from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Order
from db.requests import get_or_create_user
from bot.keyboards.reply import get_main_menu_keyboard, get_admin_panel_keyboard
from bot.keyboards.inline import get_order_support_keyboard
from config import settings

router = Router()

STATUS_LABELS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "✅ Оплачен",
    "cooking": "👩‍🍳 В сборке",
    "completed": "📦 Выполнен",
}

DELIVERY_LABELS = {
    "delivery": "🚗 Доставка",
    "pickup": "🏪 Самовывоз",
}


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Register user on first launch and show the main menu."""
    await get_or_create_user(
        session,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await message.answer(
        "Добро пожаловать в цветочный магазин! 🌸\n\n"
        "Воспользуйтесь меню ниже для навигации.",
        reply_markup=get_main_menu_keyboard(message.from_user.id),
    )


@router.message(F.text == "🌸 Каталог")
async def main_menu_catalog(message: Message, session: AsyncSession) -> None:
    from bot.handlers.catalog import show_categories
    await show_categories(message, session)


@router.message(F.text == "🛒 Корзина")
async def main_menu_cart(message: Message, session: AsyncSession, state: FSMContext) -> None:
    from bot.handlers.cart import show_cart
    await show_cart(message, session, state)


@router.message(F.text == "ℹ️ О нас / Контакты")
async def show_contacts(message: Message) -> None:
    await message.answer(
        "💐 *О нашем магазине*\n\n"
        "Мы создаём авторские букеты из свежих цветов каждый день.\n"
        "Гарантируем стойкость букетов от 5 дней.\n\n"
        "📍 *Адрес:* г. Москва, ул. Ленина, д. 10\n"
        "📞 *Телефон:* +7 (999) 123-45-67\n"
        "⏰ *Режим работы:* ежедневно с 09:00 до 21:00\n\n"
        "🚚 Доставка по городу в течение 2 часов после оплаты!",
        parse_mode="Markdown",
    )


@router.message(F.text == "📦 Мои заказы")
async def show_user_orders(message: Message, session: AsyncSession) -> None:
    """Show last 10 orders with support button on each."""
    stmt = (
        select(Order)
        .where(Order.user_id == message.from_user.id)
        .order_by(Order.id.desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        await message.answer("У вас ещё нет заказов. Время порадовать близких! 🌸")
        return

    for order in orders:
        status = STATUS_LABELS.get(order.status, order.status)
        delivery = DELIVERY_LABELS.get(order.delivery_type, order.delivery_type)
        date_line = f"📅 Дата получения: {order.desired_date}\n" if order.desired_date else ""

        text = (
            f"*Заказ №{order.id}*\n"
            f"💰 Сумма: {order.total_price:.0f} руб.\n"
            f"🚚 Тип: {delivery}\n"
            f"{date_line}"
            f"📌 Статус: {status}"
        )
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=get_order_support_keyboard(order.id),
        )


# ---------------------------------------------------------------------------
# Admin panel — sub-menu
# ---------------------------------------------------------------------------

@router.message(F.text == "📊 Админ-панель")
async def open_admin_panel(message: Message) -> None:
    """Switch keyboard to admin sub-menu."""
    if message.from_user.id != settings.ADMIN_ID:
        return
    await message.answer(
        "📊 *Админ-панель*\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_panel_keyboard(),
    )


@router.message(F.text == "⬅️ Назад в меню")
async def back_to_main_menu(message: Message) -> None:
    """Return to the main user menu."""
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_menu_keyboard(message.from_user.id),
    )


@router.message(F.text == "➕ Добавить товар")
async def add_product_from_menu(message: Message, state: FSMContext) -> None:
    """Trigger add-product wizard from the reply keyboard."""
    if message.from_user.id != settings.ADMIN_ID:
        return
    from bot.handlers.admin import start_add_product
    await start_add_product(message, state)


@router.message(F.text == "📋 Все заказы")
async def all_orders_from_menu(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Open admin order browser from the reply keyboard."""
    if message.from_user.id != settings.ADMIN_ID:
        return
    from bot.handlers.admin import browse_orders
    await browse_orders(message, session, state)