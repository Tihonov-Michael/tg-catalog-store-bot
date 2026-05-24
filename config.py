import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", 0))
    DB_URL: str = "sqlite+aiosqlite:///db.sqlite3"

    # Set to True to use real Telegram Stars payment.
    # Set to False for demo mode (simulated payment button).
    USE_REAL_PAYMENT: bool = os.getenv("USE_REAL_PAYMENT", "false").lower() == "true"

    def __post_init__(self) -> None:
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in .env file")


settings = Settings()