from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import db.requests as req
from bot.keyboards.inline import get_cart_keyboard, CartCallback
from bot.states import CartStates

router = Router()


async def _render_cart(
    user_id: int,
    session: AsyncSession,
    promo_discount: float = 0.0,
) -> tuple[str, object]:
    """Build cart message text and keyboard. Returns (text, keyboard or None)."""
    items = await req.get_cart_items(session, user_id)

    if not items:
        return "Ваша корзина пуста. Начните покупки с раздела «🌸 Каталог» 🌸", None

    text = "🛒 *Ваша корзина:*\n\n"
    subtotal = 0.0

    for item in items:
        item_total = item.product.price * item.quantity
        subtotal += item_total
        text += (
            f"• {item.product.title}\n"
            f"  `{item.quantity} шт. × {item.product.price:.0f} руб. = {item_total:.0f} руб.`\n"
        )

    text += f"\n*Подитог:* {subtotal:.0f} руб."

    if promo_discount > 0:
        discount_amount = subtotal * (promo_discount / 100)
        total = subtotal - discount_amount
        text += f"\n*Скидка:* {promo_discount}%\n*Итого:* {total:.0f} руб."
    else:
        text += f"\n*Итого:* {subtotal:.0f} руб."

    return text, get_cart_keyboard(items)


@router.message(Command("cart"))
async def show_cart(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Display the user's current cart."""
    # Do NOT clear state here — it would wipe the applied promo discount
    data = await state.get_data()
    discount = data.get("discount", 0.0)

    text, keyboard = await _render_cart(message.from_user.id, session, discount)
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(CartCallback.filter())
async def process_cart_action(
    callback: CallbackQuery,
    callback_data: CartCallback,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle +/- and delete actions on cart items."""
    await req.update_cart_quantity(session, callback_data.item_id, callback_data.action)

    data = await state.get_data()
    discount = data.get("discount", 0.0)

    text, keyboard = await _render_cart(callback.from_user.id, session, discount)

    if keyboard is None:
        # Cart is now empty — remove inline buttons
        await callback.message.edit_text(text)
    else:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data == "apply_promo")
async def prompt_promo(callback: CallbackQuery, state: FSMContext) -> None:
    """Enter FSM state to receive a promo code from the user."""
    await state.set_state(CartStates.entering_promo)
    await callback.message.answer(
        "Введите промокод (например, `SPRING10`):",
        parse_mode="Markdown",
    )
    await callback.answer()


@router.message(CartStates.entering_promo)
async def apply_promo(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Validate the promo code and store the discount in FSM data."""
    code = message.text.strip().upper()
    promo = await req.get_promo_code(session, code)

    if not promo:
        await message.answer(
            "❌ Промокод не найден или истёк. Попробуйте ещё раз или вернитесь в /cart."
        )
        return

    if promo.discount_type == "percent":
        await state.update_data(discount=promo.value)
        await message.answer(f"✅ Промокод применён! Скидка {promo.value}%.")
    else:
        # Fixed-amount discounts stored separately for potential future use
        await state.update_data(discount_fixed=promo.value)
        await message.answer(f"✅ Промокод применён! Скидка {promo.value:.0f} руб.")

    # Exit promo input state and show updated cart
    await state.set_state(None)
    data = await state.get_data()
    discount = data.get("discount", 0.0)
    text, keyboard = await _render_cart(message.from_user.id, session, discount)
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)