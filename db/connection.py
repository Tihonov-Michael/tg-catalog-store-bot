from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from config import settings

# Single async engine for the entire application
engine = create_async_engine(
    url=settings.DB_URL,
    echo=False,  # Set True to log SQL queries to console
)

# Session factory — used by DbSessionMiddleware and async_main
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def async_main() -> None:
    """Create all database tables on startup if they don't exist."""
    async with engine.begin() as conn:
        from db.base import Base
        import db.models  # noqa: F401 — ensure all models are registered on Base
        await conn.run_sync(Base.metadata.create_all)