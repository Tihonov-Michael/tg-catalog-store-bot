from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states import SupportStates
from db.requests import create_support_message
from config import settings

router = Router()


@router.callback_query(F.data.startswith("support_order_"))
async def ask_support_question(callback: CallbackQuery, state: FSMContext) -> None:
    """Enter FSM to collect a support message tied to an order."""
    order_id = int(callback.data.split("_")[2])
    await state.update_data(support_order_id=order_id)
    await state.set_state(SupportStates.waiting_for_message)
    await callback.message.answer(
        f"✍️ Напишите ваш вопрос по заказу №{order_id}.\n"
        "Администратор ответит вам в ближайшее время."
    )
    await callback.answer()


@router.message(SupportStates.waiting_for_message)
async def receive_support_message(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Save message to DB and forward to admin."""
    data = await state.get_data()
    order_id = data.get("support_order_id")
    text = message.text.strip()

    if not text:
        await message.answer("Пожалуйста, напишите текстовое сообщение.")
        return

    await create_support_message(session, message.from_user.id, text, order_id)
    await state.clear()

    await message.answer(
        "✅ Ваш вопрос отправлен. Мы свяжемся с вами в ближайшее время!"
    )

    # Forward to admin
    if settings.ADMIN_ID > 0:
        user = message.from_user
        order_line = f"📦 По заказу №{order_id}\n" if order_id else ""
        try:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            kb = InlineKeyboardBuilder()
            kb.button(
                text=f"↩️ Ответить",
                callback_data=f"reply_user_{message.from_user.id}",
            )
            await bot.send_message(
                chat_id=settings.ADMIN_ID,
                text=(
                    f"💬 *Вопрос от клиента*\n\n"
                    f"👤 {user.first_name or '—'} (@{user.username or '—'})\n"
                    f"{order_line}"
                    f"✉️ {text}"
                ),
                parse_mode="Markdown",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("reply_user_"))
async def prompt_admin_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """Admin taps Reply — enter FSM to type a response."""
    if callback.from_user.id != settings.ADMIN_ID:
        return
    user_id = int(callback.data.split("_")[2])
    await state.update_data(reply_to_user_id=user_id)
    await state.set_state(SupportStates.waiting_for_message)
    await callback.message.answer(
        f"Напишите ответ пользователю (id: {user_id}):"
    )
    await callback.answer()