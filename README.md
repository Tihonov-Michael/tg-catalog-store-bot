# 🌸 Telegram Flower Shop Bot

[🇷🇺 Читать на русском](README.ru.md)

A Telegram bot for a flower shop with a full customer journey: browsing a catalog, managing a cart, placing orders with delivery date selection, and simulated or real Telegram Stars payment. Includes a complete admin panel for catalog and order management.

Built as a portfolio project demonstrating real-world bot architecture with aiogram 3, SQLAlchemy async ORM, and FSM-driven user flows.

## Features

### Customer
- 🌸 Browse catalog by category with photo support and pagination
- 🛒 Cart management — add, remove, adjust quantity
- 🎟 Promo code support (percent and fixed discounts)
- 📅 Delivery date selection (next 5 available days)
- 📦 Order placement with delivery type, address, phone, and date
- ✅ Order confirmation screen before submitting
- 💳 Payment via Telegram Stars (real) or simulated demo button (switchable)
- 📋 Order history with status tracking
- ❓ Support questions tied to specific orders

### Admin
- 📊 Admin panel via reply keyboard (no commands needed)
- 📋 Browse all orders with full details and pagination
- ➕ Add products via FSM wizard (title, description, price, category, photo)
- ✏️ Edit any product field individually
- 🗑 Delete products from the catalog
- 🔔 Instant notifications on new paid orders with customer details
- 🔧 Update order status (In progress → Completed) with automatic customer notification

## Tech Stack

| Tool | Purpose |
|------|---------|
| [aiogram 3](https://docs.aiogram.dev/) | Async Telegram Bot framework |
| [SQLAlchemy 2 (async)](https://docs.sqlalchemy.org/) | ORM with async engine |
| [aiosqlite](https://aiosqlite.omnilib.dev/) | Async SQLite driver |
| [Alembic](https://alembic.sqlalchemy.org/) | Database migrations |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Environment variable management |

## Project Structure

```
tg-catalog-store-bot/
├── bot/
│   ├── handlers/
│   │   ├── start.py        # Main menu, contacts, order history
│   │   ├── catalog.py      # Category and product browsing
│   │   ├── cart.py         # Cart management and promo codes
│   │   ├── order.py        # Checkout FSM, payment, order creation
│   │   ├── admin.py        # Admin panel: orders, products
│   │   └── support.py      # Customer support messages
│   ├── keyboards/
│   │   ├── reply.py        # Main menu and admin panel keyboards
│   │   └── inline.py       # Catalog, cart, order, and admin keyboards
│   ├── middlewares/
│   │   ├── db.py           # SQLAlchemy session injection
│   │   └── throttling.py   # Rate limiting
│   └── states.py           # FSM state groups
├── db/
│   ├── base.py             # DeclarativeBase
│   ├── connection.py       # Engine, session factory, table creation
│   ├── models.py           # ORM models
│   └── requests.py         # Database query functions
├── migrations/             # Alembic migrations
├── config.py               # Settings loaded from .env
├── main.py                 # Entry point
├── seed.py                 # Demo data seeder
├── .env.example
└── requirements.txt
```

## Getting Started

### Prerequisites

- Python 3.11+
- Telegram bot token from [@BotFather](https://t.me/BotFather)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Tihonov-Michael/tg-catalog-store-bot.git
cd tg-catalog-store-bot
```

2. Create and activate virtual environment:
```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux / macOS
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```
BOT_TOKEN=your_token_here
ADMIN_ID=your_telegram_id
USE_REAL_PAYMENT=false
```

5. Seed the database with demo products:
```bash
python seed.py
```

6. Run the bot:
```bash
python main.py
```

## Payment Modes

Controlled by `USE_REAL_PAYMENT` in `.env`:

| Value | Behaviour |
|-------|-----------|
| `false` | Demo button — simulates payment instantly, no real transaction |
| `true` | Real Telegram Stars invoice via `send_invoice` |

## Security

- All database queries use SQLAlchemy ORM with parameterized statements — SQL injection protected
- Rate limiting via middleware — spam protected
- User data is strictly isolated by `user_id`
- Admin actions are gated by `ADMIN_ID` check on every handler
- Bot token and admin ID stored in `.env`, excluded from version control

## License

MIT
