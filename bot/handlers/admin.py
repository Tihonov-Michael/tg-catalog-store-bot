from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.keyboards.inline import AdminOrderCallback, get_fsm_keyboard, get_admin_order_keyboard
from bot.states import AdminStates
from bot.handlers.order import _finalize_order
from db.models import Product, Order
from db.requests import get_all_orders, get_order_with_items
from config import settings

router = Router()

DELIVERY_LABELS = {
    "delivery": "🚗 Доставка",
    "pickup": "🏪 Самовывоз",
}

STATUS_LABELS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "✅ Оплачен",
    "cooking": "👩‍🍳 В сборке",
    "completed": "📦 Выполнен",
}


# ---------------------------------------------------------------------------
# Payment simulation (accessible to all users — triggered from order handler)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("pay_"))
async def process_demo_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Demo payment handler — simulates successful payment."""
    order_id = int(callback.data.split("_")[1])
    order = await session.get(Order, order_id)

    if not order or order.status != "pending_payment":
        await callback.answer("Заказ уже оплачен или не найден.", show_alert=True)
        return

    await _finalize_order(order_id, callback.from_user, session, bot)

    await callback.message.edit_text(
        f"🎉 Заказ №{order_id} успешно оплачен!\n"
        "Ожидайте уведомления о сборке.",
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment_simulation(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Mark the order as paid and notify the admin."""
    order_id = int(callback.data.split("_")[1])
    order = await session.get(Order, order_id)

    if not order or order.status != "pending_payment":
        await callback.answer("Ошибка: заказ не найден или уже оплачен.", show_alert=True)
        return

    order.status = "paid"
    await session.commit()

    await callback.message.edit_text(
        f"🎉 Оплата заказа №{order_id} успешно получена!\n"
        f"Статус обновлён на: *Оплачен*. Ожидайте уведомления о сборке.",
        parse_mode="Markdown",
    )
    await callback.answer()

    # Notify the admin about the new paid order
    if settings.ADMIN_ID > 0:
        try:
            adm_kb = InlineKeyboardBuilder()
            adm_kb.button(text="🔧 В сборку", callback_data=f"adm_status_{order.id}_cooking")
            adm_kb.button(text="✅ Завершить", callback_data=f"adm_status_{order.id}_completed")
            adm_kb.adjust(1)

            await bot.send_message(
                chat_id=settings.ADMIN_ID,
                text=(
                    f"🔔 *Новый оплаченный заказ №{order.id}!*\n\n"
                    f"Сумма: {order.total_price:.0f} руб.\n"
                    f"Тип: {order.delivery_type}\n"
                    f"Адрес: {order.address}"
                ),
                parse_mode="Markdown",
                reply_markup=adm_kb.as_markup(),
            )
        except Exception:
            pass  # Don't crash if admin notification fails


# ---------------------------------------------------------------------------
# Admin: order status management
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("adm_status_"))
async def process_admin_status_update(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Update order status from the admin notification message."""
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    # Callback data format: adm_status_{order_id}_{new_status}
    parts = callback.data.split("_")
    order_id = int(parts[2])
    new_status = parts[3]

    order = await session.get(Order, order_id)
    if not order:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    status_labels = {"cooking": "В сборке", "completed": "Выполнен / Доставлен"}

    order.status = new_status
    await session.commit()

    await callback.message.edit_text(
        callback.message.text + f"\n\n⚙️ *Статус изменён на:* {status_labels.get(new_status, new_status)}",
        parse_mode="Markdown",
    )
    await callback.answer("Статус заказа обновлён.")

    # Notify the customer about the status change
    try:
        await bot.send_message(
            chat_id=order.user_id,
            text=f"📢 Статус вашего заказа №{order_id} изменён на: *{status_labels.get(new_status, new_status)}*!",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Admin: dashboard
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def show_admin_dashboard(message: Message, session: AsyncSession) -> None:
    """Show the last 5 orders. Admin only."""
    if message.from_user.id != settings.ADMIN_ID:
        return

    stmt = select(Order).order_by(Order.id.desc()).limit(5)
    result = await session.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        await message.answer("Активных заказов в базе нет.")
        return

    text = "📊 *Последние 5 заказов:*\n\n"
    for order in orders:
        text += f"• Заказ №{order.id} — {order.total_price:.0f} руб. | `{order.status}`\n"

    await message.answer(text, parse_mode="Markdown")


# ---------------------------------------------------------------------------
# Admin: add product wizard
# ---------------------------------------------------------------------------

@router.message(Command("add_product"))
async def start_add_product(message: Message, state: FSMContext) -> None:
    """Start the FSM wizard to add a new product. Admin only."""
    if message.from_user.id != settings.ADMIN_ID:
        return

    await state.set_state(AdminStates.waiting_for_title)
    await message.answer(
        "📝 Введите *название* нового товара:",
        parse_mode="Markdown",
        reply_markup=get_fsm_keyboard(is_first_step=True),
    )


@router.message(AdminStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminStates.waiting_for_description)
    await message.answer(
        "✍️ Введите *описание* товара:",
        parse_mode="Markdown",
        reply_markup=get_fsm_keyboard(),
    )


@router.message(AdminStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminStates.waiting_for_price)
    await message.answer(
        "💰 Введите *цену* (например: 3200):",
        parse_mode="Markdown",
        reply_markup=get_fsm_keyboard(),
    )


@router.message(AdminStates.waiting_for_price)
async def process_price(message: Message, state: FSMContext) -> None:
    try:
        price = float(message.text.replace(",", ".").strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Некорректная цена. Введите положительное число:")
        return

    await state.update_data(price=price)
    await state.set_state(AdminStates.waiting_for_category)
    await message.answer(
        "📁 Введите *категорию* (например: Розы, Тюльпаны, Миксы):",
        parse_mode="Markdown",
        reply_markup=get_fsm_keyboard(),
    )


@router.message(AdminStates.waiting_for_category)
async def process_category(message: Message, state: FSMContext) -> None:
    await state.update_data(category=message.text.strip().capitalize())
    await state.set_state(AdminStates.waiting_for_image)
    await message.answer(
        "📸 Отправьте фотографию товара:",
        reply_markup=get_fsm_keyboard(show_skip=True),
    )


@router.message(AdminStates.waiting_for_image, F.photo)
async def process_image_and_save(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Save the product with the highest-resolution photo available."""
    data = await state.get_data()
    product = Product(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        category=data["category"],
        image_id=message.photo[-1].file_id,
    )
    session.add(product)
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ Товар успешно добавлен!\n\n"
        f"🌸 *{product.title}*\n"
        f"📁 {product.category} | 💰 {product.price:.0f} руб.",
        parse_mode="Markdown",
    )


@router.callback_query(AdminStates.waiting_for_image, F.data == "skip_photo")
async def process_skip_photo(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Save the product without a photo."""
    data = await state.get_data()
    product = Product(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        category=data["category"],
        image_id=None,
    )
    session.add(product)
    await session.commit()
    await state.clear()

    await callback.message.edit_text(
        f"✅ Товар *{product.title}* добавлен без фото.",
        parse_mode="Markdown",
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Admin: delete product
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("adm_delete_prod_"))
async def admin_delete_product(callback: CallbackQuery, session: AsyncSession) -> None:
    """Hard-delete a product from the catalog."""
    if callback.from_user.id != settings.ADMIN_ID:
        return

    product_id = int(callback.data.split("_")[3])
    product = await session.get(Product, product_id)

    if product:
        await session.delete(product)
        await session.commit()
        await callback.answer("🗑 Товар удалён из каталога.", show_alert=True)
        await callback.message.delete()
        await callback.message.answer("Товар удалён. Откройте /catalog для обновления списка.")
    else:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)


# ---------------------------------------------------------------------------
# Admin: edit product
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("adm_edit_choice_"))
async def admin_edit_menu(callback: CallbackQuery) -> None:
    """Show a menu to choose which product field to edit."""
    if callback.from_user.id != settings.ADMIN_ID:
        return

    product_id = int(callback.data.split("_")[3])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Название", callback_data=f"field_title_{product_id}"),
            InlineKeyboardButton(text="💰 Цена", callback_data=f"field_price_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="✍️ Описание", callback_data=f"field_description_{product_id}"),
            InlineKeyboardButton(text="📸 Фото", callback_data=f"field_image_{product_id}"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_categories")],
    ])

    await callback.message.answer("Что хотите изменить в этом товаре?", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("field_"))
async def admin_prompt_field_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """Set FSM to wait for the new field value."""
    # Callback data format: field_{field_type}_{product_id}
    _, field_type, product_id = callback.data.split("_")

    await state.set_state(AdminStates.waiting_for_edit_value)
    await state.update_data(edit_product_id=int(product_id), edit_field_type=field_type)

    prompts = {
        "title": "📝 Введите *новое название:*",
        "price": "💰 Введите *новую цену* (число):",
        "description": "✍️ Введите *новое описание:*",
        "image": "📸 Отправьте *новую фотографию* (именно как фото, не файл):",
    }

    await callback.message.answer(
        prompts.get(field_type, "Введите новое значение:"),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_edit_value)
async def admin_process_edit(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Apply the new value to the selected product field."""
    data = await state.get_data()
    product = await session.get(Product, data["edit_product_id"])

    if not product:
        await message.answer("❌ Товар не найден в базе данных.")
        await state.clear()
        return

    field_type = data["edit_field_type"]

    if field_type == "title":
        product.title = message.text.strip()

    elif field_type == "description":
        product.description = message.text.strip()

    elif field_type == "price":
        try:
            price = float(message.text.replace(",", ".").strip())
            if price <= 0:
                raise ValueError
            product.price = price
        except ValueError:
            await message.answer("❌ Некорректная цена. Введите число:")
            return

    elif field_type == "image":
        if not message.photo:
            await message.answer("❌ Это не фотография. Отправьте изображение:")
            return
        product.image_id = message.photo[-1].file_id

    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ Товар *{product.title}* обновлён.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# FSM navigation helpers
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "fsm_cancel")
async def fsm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the current FSM wizard."""
    await state.clear()
    await callback.message.edit_text("❌ Добавление товара отменено.")
    await callback.answer()


@router.callback_query(F.data == "fsm_back")
async def fsm_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Go back one step in the add-product wizard."""
    current = await state.get_state()

    steps_back = {
        AdminStates.waiting_for_description: AdminStates.waiting_for_title,
        AdminStates.waiting_for_price: AdminStates.waiting_for_description,
        AdminStates.waiting_for_category: AdminStates.waiting_for_price,
        AdminStates.waiting_for_image: AdminStates.waiting_for_category,
    }

    previous = steps_back.get(current)
    if not previous:
        await callback.answer()
        return

    await state.set_state(previous)
    await callback.message.delete()

    prompts = {
        AdminStates.waiting_for_title: "📝 Введите название:",
        AdminStates.waiting_for_description: "✍️ Введите описание:",
        AdminStates.waiting_for_price: "💰 Введите цену:",
        AdminStates.waiting_for_category: "📁 Введите категорию:",
    }

    await callback.message.answer(
        prompts.get(previous, "Продолжаем..."),
        reply_markup=get_fsm_keyboard(is_first_step=(previous == AdminStates.waiting_for_title)),
    )
    await callback.answer()

async def browse_orders(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Entry point: load all orders and show the first one."""
    orders = await get_all_orders(session)
    if not orders:
        await message.answer("Заказов пока нет.")
        return

    await state.set_state(AdminStates.browsing_orders)
    await _show_order(message, session, state, orders, 0)


async def _show_order(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    orders: list,
    index: int,
) -> None:
    """Render a single order card with navigation keyboard."""
    order = await get_order_with_items(session, orders[index].id)
    await state.update_data(order_index=index, order_ids=[o.id for o in orders])

    delivery = DELIVERY_LABELS.get(order.delivery_type, order.delivery_type)
    status = STATUS_LABELS.get(order.status, order.status)
    phone = order.user.phone if order.user else "—"
    name = order.user.first_name if order.user else "—"
    username = f"@{order.user.username}" if order.user and order.user.username else "—"

    items_text = "\n".join(
        f"  • {item.product.title} × {item.quantity} — {item.price_at_creation * item.quantity:.0f} руб."
        for item in order.items
    )

    text = (
        f"📦 *Заказ №{order.id}*\n\n"
        f"👤 Клиент: {name} ({username})\n"
        f"📱 Телефон: {phone}\n"
        f"🚚 Тип: {delivery}\n"
        f"📍 Адрес: {order.address or '—'}\n"
        f"📅 Дата: {order.desired_date or '—'}\n"
        f"📌 Статус: {status}\n"
        f"💰 Сумма: {order.total_price:.0f} руб.\n\n"
        f"🌸 Состав заказа:\n{items_text}"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=get_admin_order_keyboard(index, len(orders), order.id, order.status),
    )


@router.callback_query(AdminOrderCallback.filter())
async def paginate_orders(
    callback: CallbackQuery,
    callback_data: AdminOrderCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle order pagination and boundary popups."""
    if callback.from_user.id != settings.ADMIN_ID:
        return

    action = callback_data.action

    if action == "boundary_left":
        await callback.answer("Это первый заказ.", show_alert=True)
        return
    if action == "boundary_right":
        await callback.answer("Это последний заказ.", show_alert=True)
        return
    if action == "noop":
        await callback.answer()
        return

    data = await state.get_data()
    order_ids = data.get("order_ids", [])

    if not order_ids:
        await callback.answer("Список заказов устарел. Откройте раздел заново.")
        return

    # Reload orders to reflect any status changes
    from db.models import Order as OrderModel
    from sqlalchemy import select as sa_select
    stmt = sa_select(OrderModel).where(
        OrderModel.id.in_(order_ids)
    ).order_by(OrderModel.id.desc())
    result = await session.execute(stmt)
    orders = result.scalars().all()

    await callback.message.delete()
    await _show_order(callback.message, session, state, orders, callback_data.index)
    await callback.answer()