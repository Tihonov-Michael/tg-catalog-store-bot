from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import settings


def get_main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Main menu for all users. Admin gets an extra row."""
    keyboard = [
        [KeyboardButton(text="🌸 Каталог"), KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="ℹ️ О нас / Контакты")],
    ]
    if user_id == settings.ADMIN_ID:
        keyboard.append([KeyboardButton(text="📊 Админ-панель")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, persistent=True)


def get_admin_panel_keyboard() -> ReplyKeyboardMarkup:
    """Admin sub-menu opened by the '📊 Админ-панель' button."""
    keyboard = [
        [KeyboardButton(text="📋 Все заказы")],
        [KeyboardButton(text="➕ Добавить товар")],
        [KeyboardButton(text="⬅️ Назад в меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, persistent=True)