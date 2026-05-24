from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.states import OrderStates
from bot.keyboards.inline import get_order_confirm_keyboard, get_date_keyboard
from db.models import CartItem, Order, OrderItem
from db.requests import update_user_phone, get_cart_items
from config import settings

router = Router()

_DELIVERY_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚗 Доставка"), KeyboardButton(text="🏪 Самовывоз")]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

_PHONE_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)

DELIVERY_LABELS = {
    "delivery": "🚗 Доставка",
    "pickup": "🏪 Самовывоз",
}


def _build_order_summary(data: dict) -> str:
    """Build a human-readable order summary from FSM data."""
    delivery = DELIVERY_LABELS.get(data.get("delivery_type", ""), "—")
    address = data.get("address", "—")
    desired_date = data.get("desired_date", "—")
    phone = data.get("phone", "—")
    discount = data.get("discount", 0.0)
    subtotal = data.get("subtotal", 0.0)
    total = subtotal * (1 - discount / 100)

    lines = [
        "📋 *Детали вашего заказа:*\n",
        f"🚚 Способ получения: {delivery}",
    ]
    if data.get("delivery_type") == "delivery":
        lines.append(f"📍 Адрес: {address}")
    lines.append(f"📅 Желаемая дата: {desired_date}")
    lines.append(f"📱 Телефон: {phone}")
    if discount > 0:
        lines.append(f"🎟 Скидка: {discount}%")
    lines.append(f"\n💰 Итого к оплате: *{total:.0f} руб.*")
    return "\n".join(lines)


@router.callback_query(F.data == "checkout")
async def start_checkout(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    """Begin checkout if cart is not empty."""
    stmt = select(CartItem).where(CartItem.user_id == callback.from_user.id)
    result = await session.execute(stmt)
    if not result.scalars().first():
        await callback.answer("Ваша корзина пуста!", show_alert=True)
        return

    items = await get_cart_items(session, callback.from_user.id)
    subtotal = sum(item.product.price * item.quantity for item in items)
    await state.update_data(subtotal=subtotal)

    await state.set_state(OrderStates.choosing_delivery_type)
    await callback.message.answer(
        "Выберите способ получения заказа:",
        reply_markup=_DELIVERY_KB,
    )
    await callback.answer()


@router.message(
    OrderStates.choosing_delivery_type,
    F.text.in_(["🚗 Доставка", "🏪 Самовывоз"]),
)
async def process_delivery_type(message: Message, state: FSMContext) -> None:
    if message.text == "🚗 Доставка":
        await state.update_data(delivery_type="delivery")
        await state.set_state(OrderStates.entering_address)
        await message.answer(
            "Введите адрес доставки (город, улица, дом, квартира):",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await state.update_data(
            delivery_type="pickup",
            address="Главный филиал (ул. Ленина, 10)",
        )
        await state.set_state(OrderStates.choosing_date)
        await message.answer(
            "Выберите желаемую дату получения:",
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            "📅 Доступные даты:",
            reply_markup=get_date_keyboard(),
        )


@router.message(OrderStates.entering_address)
async def process_address(message: Message, state: FSMContext) -> None:
    await state.update_data(address=message.text.strip())
    await state.set_state(OrderStates.choosing_date)
    await message.answer(
        "📅 Выберите желаемую дату доставки:",
        reply_markup=get_date_keyboard(),
    )


@router.callback_query(F.data.startswith("date_"), OrderStates.choosing_date)
async def process_date(callback: CallbackQuery, state: FSMContext) -> None:
    """Save chosen date and ask for phone number."""
    chosen_date = callback.data.split("_", 1)[1]  # "date_22.05.2025" → "22.05.2025"
    await state.update_data(desired_date=chosen_date)
    await state.set_state(OrderStates.entering_phone)

    await callback.message.answer(
        f"✅ Дата выбрана: *{chosen_date}*\n\n"
        "Теперь поделитесь номером телефона для подтверждения:",
        parse_mode="Markdown",
        reply_markup=_PHONE_KB,
    )
    await callback.answer()


@router.message(OrderStates.entering_phone, F.contact)
async def process_phone(message: Message, state: FSMContext) -> None:
    """Save phone and show order summary for confirmation."""
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(OrderStates.confirming_order)

    data = await state.get_data()
    summary = _build_order_summary(data)

    await message.answer(
        f"{summary}\n\n"
        "Проверьте данные и подтвердите заказ.",
        parse_mode="Markdown",
        reply_markup=get_order_confirm_keyboard(),
    )


@router.callback_query(F.data == "order_edit")
async def order_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Restart checkout from delivery type selection."""
    await state.set_state(OrderStates.choosing_delivery_type)
    await callback.message.answer(
        "Начнём заново. Выберите способ получения:",
        reply_markup=_DELIVERY_KB,
    )
    await callback.answer()


@router.callback_query(F.data == "order_confirm")
async def order_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Create order in DB, then either send Stars invoice or demo button."""
    data = await state.get_data()

    await update_user_phone(session, callback.from_user.id, data.get("phone", ""))

    items = await get_cart_items(session, callback.from_user.id)
    subtotal = data.get("subtotal", 0.0)
    discount_pct = data.get("discount", 0.0)
    total_price = round(subtotal * (1 - discount_pct / 100), 2)

    order = Order(
        user_id=callback.from_user.id,
        total_price=total_price,
        delivery_type=data["delivery_type"],
        address=data.get("address"),
        desired_date=data.get("desired_date"),
        status="pending_payment",
    )
    session.add(order)
    await session.flush()

    for item in items:
        session.add(OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price_at_creation=item.product.price,
        ))
        await session.delete(item)

    await session.commit()
    await state.clear()

    await callback.message.answer(
        f"✅ Заказ №{order.id} оформлен!\n"
        "Осталось оплатить 👇",
        reply_markup=ReplyKeyboardRemove(),
    )

    if settings.USE_REAL_PAYMENT:
        # Real Telegram Stars invoice
        stars_amount = max(1, int(total_price / 100))
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Заказ №{order.id} — Цветочный магазин",
            description=(
                f"{DELIVERY_LABELS.get(order.delivery_type, '—')}\n"
                f"Дата: {order.desired_date or '—'}\n"
                f"Сумма: {order.total_price:.0f} руб."
            ),
            payload=f"order_{order.id}",
            currency="XTR",
            prices=[{"label": f"Заказ №{order.id}", "amount": stars_amount}],
        )
    else:
        # Demo mode — simulated payment button
        demo_kb = InlineKeyboardBuilder()
        demo_kb.button(
            text=f"💳 Оплатить {total_price:.0f} руб. (демо)",
            callback_data=f"pay_{order.id}",
        )
        await callback.message.answer(
            f"*Сумма к оплате: {total_price:.0f} руб.*\n\n"
            "⚠️ Это демо-режим. Нажмите кнопку для имитации оплаты.",
            parse_mode="Markdown",
            reply_markup=demo_kb.as_markup(),
        )

    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query, bot: Bot) -> None:
    """Always approve pre-checkout (Stars payment)."""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Handle completed Stars payment — mark order paid and notify admin."""
    order_id = int(message.successful_payment.invoice_payload.split("_")[1])
    await _finalize_order(order_id, message.from_user, session, bot)
    await message.answer(
        "🎉 Оплата прошла успешно!\n"
        "Заказ подтверждён. Ожидайте уведомления о сборке."
    )


async def _finalize_order(order_id: int, user, session: AsyncSession, bot: Bot) -> None:
    """Mark order as paid and notify admin. Used by both payment paths."""
    # Eagerly load the user relationship to avoid lazy-loading in async context
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.user))
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()

    if not order:
        return

    order.status = "paid"
    await session.commit()

    if settings.ADMIN_ID <= 0:
        return

    delivery = DELIVERY_LABELS.get(order.delivery_type, "—")
    phone = order.user.phone if order.user else "—"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔧 Взять в сборку", callback_data=f"adm_status_{order.id}_cooking")
    kb.button(text="✅ Завершить", callback_data=f"adm_status_{order.id}_completed")
    kb.adjust(1)

    try:
        await bot.send_message(
            chat_id=settings.ADMIN_ID,
            text=(
                f"🔔 *Новый оплаченный заказ №{order.id}!*\n\n"
                f"👤 Клиент: {user.first_name or '—'} (@{user.username or '—'})\n"
                f"📱 Телефон: {phone}\n"
                f"🚚 Тип: {delivery}\n"
                f"📍 Адрес: {order.address or '—'}\n"
                f"📅 Дата: {order.desired_date or '—'}\n"
                f"💰 Сумма: {order.total_price:.0f} руб."
            ),
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
        )
    except Exception:
        pass