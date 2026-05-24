from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import db.requests as req
from bot.keyboards.inline import (
    get_categories_keyboard,
    get_product_keyboard,
    CategoryCallback,
    PaginationCallback,
)
from bot.states import CartStates

router = Router()


async def show_categories(message: Message, session: AsyncSession) -> None:
    """Utility: send the category list. Called from multiple entry points."""
    categories = await req.get_categories(session)
    if not categories:
        await message.answer("Каталог пуст. Загляните позже! 🌸")
        return
    await message.answer(
        "Выберите категорию:",
        reply_markup=get_categories_keyboard(categories),
    )


@router.message(Command("catalog"))
async def cmd_catalog(message: Message, session: AsyncSession) -> None:
    await show_categories(message, session)


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.message.delete()
    await show_categories(callback.message, session)


@router.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery) -> None:
    await callback.answer("Это порядковый номер товара в категории 🌸", show_alert=True)


@router.callback_query(CategoryCallback.filter())
async def show_first_product(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    session: AsyncSession,
) -> None:
    """Display the first product in the selected category."""
    products = await req.get_products_by_category(session, callback_data.name)
    if not products:
        await callback.answer("В этой категории нет товаров.")
        return

    product = products[0]
    text = (
        f"🌸 *{product.title}*\n\n"
        f"{product.description}\n\n"
        f"Цена: *{product.price:.0f} руб.*"
    )
    kb = get_product_keyboard(
        callback_data.name, 0, len(products), product.id, callback.from_user.id
    )

    await callback.message.delete()

    if product.image_id:
        await callback.message.answer_photo(
            photo=product.image_id,
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb,
        )
    else:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)

    await callback.answer()


@router.callback_query(PaginationCallback.filter())
async def process_pagination(
    callback: CallbackQuery,
    callback_data: PaginationCallback,
    session: AsyncSession,
) -> None:
    """Handle navigation, boundary popups, and add-to-cart."""

    # Boundary popups — show alert and do nothing else
    if callback_data.action == "boundary_left":
        await callback.answer("Это первый товар в категории.", show_alert=True)
        return
    if callback_data.action == "boundary_right":
        await callback.answer("Это последний товар в категории.", show_alert=True)
        return

    products = await req.get_products_by_category(session, callback_data.category)

    # Add to cart
    if callback_data.action == "add":
        product = products[callback_data.index]
        await req.add_to_cart(session, callback.from_user.id, product.id)
        await callback.answer("✅ Товар добавлен в корзину!")
        return

    # Navigate to product at the given index
    product = products[callback_data.index]
    text = (
        f"🌸 *{product.title}*\n\n"
        f"{product.description}\n\n"
        f"Цена: *{product.price:.0f} руб.*"
    )
    kb = get_product_keyboard(
        callback_data.category,
        callback_data.index,
        len(products),
        product.id,
        callback.from_user.id,
    )

    if product.image_id:
        if callback.message.photo:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=product.image_id, caption=text, parse_mode="Markdown"
                ),
                reply_markup=kb,
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=product.image_id,
                caption=text,
                parse_mode="Markdown",
                reply_markup=kb,
            )
    else:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

    await callback.answer()


@router.callback_query(F.data.startswith("add_cart_"))
async def prompt_quantity(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split("_")[2])
    await state.update_data(cart_product_id=product_id)
    await state.set_state(CartStates.waiting_for_quantity)
    await callback.message.delete()
    await callback.message.answer("Введите количество букетов:")
    await callback.answer()


@router.message(CartStates.waiting_for_quantity)
async def process_quantity(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите целое положительное число:")
        return

    data = await state.get_data()
    await req.add_to_cart(
        session,
        message.from_user.id,
        data["cart_product_id"],
        int(message.text),
    )
    await state.clear()
    await message.answer("✅ Товар добавлен в корзину!")
    await show_categories(message, session)