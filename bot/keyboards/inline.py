from datetime import date, timedelta
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from config import settings


# ---------------------------------------------------------------------------
# Callback data factories
# ---------------------------------------------------------------------------

class CategoryCallback(CallbackData, prefix="cat"):
    name: str


class PaginationCallback(CallbackData, prefix="pag"):
    category: str
    index: int
    action: str  # "prev", "next", "add", "boundary_left", "boundary_right"


class CartCallback(CallbackData, prefix="cart"):
    item_id: int
    action: str  # "plus", "minus", "delete"


class AdminOrderCallback(CallbackData, prefix="adm_order"):
    index: int
    action: str  # "prev", "next", "noop", "boundary_left", "boundary_right"


# ---------------------------------------------------------------------------
# Catalog keyboards
# ---------------------------------------------------------------------------

def get_categories_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    """Two-column grid of product categories."""
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category, callback_data=CategoryCallback(name=category))
    builder.adjust(2)
    return builder.as_markup()


def get_product_keyboard(
    category: str,
    current_idx: int,
    total_items: int,
    product_id: int,
    user_id: int,
) -> InlineKeyboardMarkup:
    """
    Row 1 — navigation: spacer | N/Total | spacer (spacers show popup on tap)
    Row 2 — 🛒 В корзину
    Row 3 — 📁 К категориям
    Row 4 — admin controls (admin only)
    """
    builder = InlineKeyboardBuilder()

    # Row 1: left arrow or spacer
    if current_idx > 0:
        builder.button(
            text="⬅️",
            callback_data=PaginationCallback(
                category=category, index=current_idx - 1, action="prev"
            ),
        )
    else:
        builder.button(
            text=" ",
            callback_data=PaginationCallback(
                category=category, index=current_idx, action="boundary_left"
            ),
        )

    # Row 1: index indicator
    builder.button(text=f"{current_idx + 1} / {total_items}", callback_data="show_stats")

    # Row 1: right arrow or spacer
    if current_idx < total_items - 1:
        builder.button(
            text="➡️",
            callback_data=PaginationCallback(
                category=category, index=current_idx + 1, action="next"
            ),
        )
    else:
        builder.button(
            text=" ",
            callback_data=PaginationCallback(
                category=category, index=current_idx, action="boundary_right"
            ),
        )

    # Row 2: add to cart
    builder.button(
        text="🛒 В корзину",
        callback_data=PaginationCallback(
            category=category, index=current_idx, action="add"
        ),
    )

    # Row 3: back to categories
    builder.button(text="📁 К категориям", callback_data="back_to_categories")

    # Row 4: admin controls
    if user_id == settings.ADMIN_ID:
        builder.button(
            text="✏️ Редактировать",
            callback_data=f"adm_edit_choice_{product_id}",
        )
        builder.button(
            text="🗑 Удалить",
            callback_data=f"adm_delete_prod_{product_id}",
        )

    layout = [3, 1, 1]
    if user_id == settings.ADMIN_ID:
        layout.append(2)

    builder.adjust(*layout)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Date picker keyboard (next 5 days from tomorrow)
# ---------------------------------------------------------------------------

def get_date_keyboard() -> InlineKeyboardMarkup:
    """Show the next 5 available delivery dates as inline buttons."""
    builder = InlineKeyboardBuilder()
    today = date.today()

    day_names = {
        0: "Пн", 1: "Вт", 2: "Ср",
        3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс",
    }

    for i in range(1, 6):
        delivery_date = today + timedelta(days=i)
        day_name = day_names[delivery_date.weekday()]
        label = f"{day_name}, {delivery_date.strftime('%d.%m')}"
        builder.button(
            text=label,
            callback_data=f"date_{delivery_date.strftime('%d.%m.%Y')}",
        )

    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Cart keyboard
# ---------------------------------------------------------------------------

def get_cart_keyboard(cart_items: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for item in cart_items:
        builder.button(
            text=f"❌ {item.product.title}",
            callback_data=CartCallback(item_id=item.id, action="delete"),
        )
        builder.button(
            text="➖",
            callback_data=CartCallback(item_id=item.id, action="minus"),
        )
        builder.button(text=f"{item.quantity} шт.", callback_data="noop")
        builder.button(
            text="➕",
            callback_data=CartCallback(item_id=item.id, action="plus"),
        )

    builder.button(text="🎟 Применить промокод", callback_data="apply_promo")
    builder.button(text="📦 Оформить заказ", callback_data="checkout")

    layout = []
    for _ in cart_items:
        layout.extend([1, 3])
    layout.extend([1, 1])

    builder.adjust(*layout)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Order confirmation keyboard
# ---------------------------------------------------------------------------

def get_order_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="order_confirm")
    builder.button(text="✏️ Редактировать", callback_data="order_edit")
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# My orders — support question keyboard
# ---------------------------------------------------------------------------

def get_order_support_keyboard(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="❓ Вопрос по заказу",
        callback_data=f"support_order_{order_id}",
    )
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Admin orders pagination keyboard
# ---------------------------------------------------------------------------

def get_admin_order_keyboard(
    current_idx: int,
    total: int,
    order_id: int,
    order_status: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Row 1: left
    if current_idx > 0:
        builder.button(
            text="⬅️",
            callback_data=AdminOrderCallback(index=current_idx - 1, action="prev"),
        )
    else:
        builder.button(
            text=" ",
            callback_data=AdminOrderCallback(index=current_idx, action="boundary_left"),
        )

    builder.button(
        text=f"{current_idx + 1} / {total}",
        callback_data=AdminOrderCallback(index=current_idx, action="noop"),
    )

    # Row 1: right
    if current_idx < total - 1:
        builder.button(
            text="➡️",
            callback_data=AdminOrderCallback(index=current_idx + 1, action="next"),
        )
    else:
        builder.button(
            text=" ",
            callback_data=AdminOrderCallback(index=current_idx, action="boundary_right"),
        )

    # Status transition buttons
    if order_status == "paid":
        builder.button(
            text="🔧 Взять в сборку",
            callback_data=f"adm_status_{order_id}_cooking",
        )
    if order_status in ("paid", "cooking"):
        builder.button(
            text="✅ Завершить заказ",
            callback_data=f"adm_status_{order_id}_completed",
        )

    layout = [3]
    if order_status == "paid":
        layout.append(1)
    if order_status in ("paid", "cooking"):
        layout.append(1)

    builder.adjust(*layout)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# FSM wizard keyboard (add product)
# ---------------------------------------------------------------------------

def get_fsm_keyboard(
    is_first_step: bool = False,
    show_skip: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_skip:
        builder.button(text="➡️ Пропустить фото", callback_data="skip_photo")
    if not is_first_step:
        builder.button(text="⬅️ Назад", callback_data="fsm_back")
    builder.button(text="❌ Отмена", callback_data="fsm_cancel")
    builder.adjust(1)
    return builder.as_markup()