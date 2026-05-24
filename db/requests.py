from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, Product, CartItem, Order, OrderItem, PromoCode, SupportMessage


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str] = None,
) -> User:
    user = await session.get(User, telegram_id)
    if not user:
        user = User(id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.commit()
    return user


async def update_user_phone(session: AsyncSession, telegram_id: int, phone: str) -> None:
    user = await session.get(User, telegram_id)
    if user:
        user.phone = phone
        await session.commit()


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

async def get_categories(session: AsyncSession) -> List[str]:
    stmt = select(Product.category).distinct()
    result = await session.execute(stmt)
    return sorted([row[0] for row in result.all()])


async def get_products_by_category(session: AsyncSession, category: str) -> List[Product]:
    stmt = select(Product).where(Product.category == category)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_product_by_id(session: AsyncSession, product_id: int) -> Optional[Product]:
    return await session.get(Product, product_id)


# ---------------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------------

async def add_to_cart(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int = 1,
) -> None:
    stmt = select(CartItem).where(
        CartItem.user_id == user_id,
        CartItem.product_id == product_id,
    )
    result = await session.execute(stmt)
    item = result.scalar_one_or_none()

    if item:
        item.quantity += quantity
    else:
        session.add(CartItem(user_id=user_id, product_id=product_id, quantity=quantity))

    await session.commit()


async def get_cart_items(session: AsyncSession, user_id: int) -> List[CartItem]:
    stmt = (
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.product))
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_cart_quantity(session: AsyncSession, item_id: int, action: str) -> None:
    item = await session.get(CartItem, item_id)
    if not item:
        return
    if action == "plus":
        item.quantity += 1
    elif action == "minus":
        item.quantity -= 1
        if item.quantity <= 0:
            await session.delete(item)
    elif action == "delete":
        await session.delete(item)
    await session.commit()


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    stmt = delete(CartItem).where(CartItem.user_id == user_id)
    await session.execute(stmt)
    await session.commit()


# ---------------------------------------------------------------------------
# Promo codes
# ---------------------------------------------------------------------------

async def get_promo_code(session: AsyncSession, code_str: str) -> Optional[PromoCode]:
    stmt = select(PromoCode).where(
        PromoCode.code == code_str,
        PromoCode.is_active == True,  # noqa: E712
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

async def get_all_orders(session: AsyncSession) -> List[Order]:
    """Return all orders ordered by newest first."""
    stmt = select(Order).order_by(Order.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_order_with_items(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Return a single order with eagerly loaded items and products."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.user),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------

async def create_support_message(
    session: AsyncSession,
    user_id: int,
    text: str,
    order_id: Optional[int] = None,
) -> SupportMessage:
    msg = SupportMessage(user_id=user_id, order_id=order_id, text=text)
    session.add(msg)
    await session.commit()
    return msg