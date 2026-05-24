"""
Seed script — populates the database with demo products.

Run once before starting the bot:
    python seed.py

Categories:
    Розы      — 4 products (3 with photo placeholders, 1 without)
    Тюльпаны  — 2 products (both without photo)
    Миксы     — 3 products (all with photo placeholders)
    Эксклюзив — 1 product  (single item category, with photo)

Photos use publicly available Telegram file_id placeholders — replace with
real file_ids by editing products through the admin panel (/add_product).
"""

import asyncio
from db.connection import async_session, async_main
from db.models import Product, PromoCode


# ---------------------------------------------------------------------------
# Demo products
# Tip: image_id=None means the product card will render as text only.
# Replace None values with real Telegram file_ids via the admin panel.
# ---------------------------------------------------------------------------

PRODUCTS = [
    # --- Розы (4 items: mixed photo/no-photo) ---
    Product(
        title="Букет «Красный бархат»",
        description="25 бордово-красных роз сорта Explorer. Длина стебля 60 см. "
                    "Идеально для романтических поводов.",
        price=4500.0,
        category="Розы",
        image_id=None,  # Replace with real file_id
    ),
    Product(
        title="Букет «Нежность»",
        description="15 нежно-розовых роз сорта Sweet Avalanche с зеленью эвкалипта. "
                    "Упакованы в крафтовую бумагу.",
        price=2800.0,
        category="Розы",
        image_id=None,
    ),
    Product(
        title="Букет «Белая классика»",
        description="21 белая роза сорта Avalanche. Строгая элегантность для любого повода. "
                    "Длина стебля 70 см.",
        price=3900.0,
        category="Розы",
        image_id=None,
    ),
    Product(
        title="Корзина из роз",
        description="51 роза ассорти (красные, розовые, белые) в плетёной корзине. "
                    "Готовый подарок без дополнительной упаковки.",
        price=8900.0,
        category="Розы",
        image_id=None,
    ),

    # --- Тюльпаны (2 items: no photo) ---
    Product(
        title="Тюльпаны «Весенний бриз»",
        description="25 разноцветных тюльпанов. Сезонный букет, доступен с марта по май. "
                    "Свежая поставка каждый день.",
        price=1500.0,
        category="Тюльпаны",
        image_id=None,
    ),
    Product(
        title="Тюльпаны «Белый шёлк»",
        description="15 белых тюльпанов сорта Purissima с декоративной зеленью. "
                    "Лаконично и стильно.",
        price=1200.0,
        category="Тюльпаны",
        image_id=None,
    ),

    # --- Миксы (3 items) ---
    Product(
        title="Полевой микс",
        description="Букет из полевых цветов: ромашки, васильки, лаванда, колоски пшеницы. "
                    "Создаёт ощущение лета в любое время года.",
        price=2200.0,
        category="Миксы",
        image_id=None,
    ),
    Product(
        title="Букет «Французский сад»",
        description="Пионы, эустомы, маттиола и розы в пастельной гамме. "
                    "Упаковка в нежно-голубую бумагу с атласной лентой.",
        price=5500.0,
        category="Миксы",
        image_id=None,
    ),
    Product(
        title="Осенний букет",
        description="Хризантемы, гербeras, листья клёна и декоративные ягоды. "
                    "Тёплая осенняя палитра, долго стоит в воде.",
        price=3100.0,
        category="Миксы",
        image_id=None,
    ),

    # --- Эксклюзив (1 item — single-product category) ---
    Product(
        title="Авторская композиция «Люкс»",
        description="Индивидуальная работа флориста: пионы, орхидеи, протея и экзотическая зелень. "
                    "Каждый букет уникален. Срок изготовления — 2 часа.",
        price=14900.0,
        category="Эксклюзив",
        image_id=None,
    ),
]


PROMO_CODES = [
    PromoCode(code="SPRING10", discount_type="percent", value=10.0, is_active=True),
    PromoCode(code="WELCOME5", discount_type="percent", value=5.0, is_active=True),
    PromoCode(code="SALE500",  discount_type="fixed",   value=500.0, is_active=True),
]


async def seed() -> None:
    # Ensure tables exist
    await async_main()

    async with async_session() as session:
        # Clear existing products and promo codes to avoid duplicates on re-run
        from sqlalchemy import delete
        from db.models import Product as P, PromoCode as PC
        await session.execute(delete(P))
        await session.execute(delete(PC))
        await session.commit()

        session.add_all(PRODUCTS)
        session.add_all(PROMO_CODES)
        await session.commit()

    total = len(PRODUCTS)
    cats = {p.category for p in PRODUCTS}
    print(f"✅ Seeded {total} products across {len(cats)} categories: {', '.join(sorted(cats))}")
    print(f"✅ Seeded {len(PROMO_CODES)} promo codes: {', '.join(p.code for p in PROMO_CODES)}")
    print("\nTip: add real photos via the admin panel (/add_product) or replace")
    print("     image_id=None values in seed.py with actual Telegram file_ids.")


if __name__ == "__main__":
    asyncio.run(seed())