import time
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)

RATE_LIMIT = 1.5       # Minimum seconds between requests per user
CLEANUP_INTERVAL = 300  # Clear stale entries every 5 minutes


class ThrottlingMiddleware(BaseMiddleware):
    """Rate-limit middleware: silently drops messages that arrive too fast."""

    def __init__(self, rate_limit: float = RATE_LIMIT) -> None:
        self.rate_limit = rate_limit
        self.users: Dict[int, float] = {}
        self._last_cleanup = time.monotonic()

    def _cleanup(self, now: float) -> None:
        """Remove entries older than CLEANUP_INTERVAL to prevent memory growth."""
        if now - self._last_cleanup < CLEANUP_INTERVAL:
            return
        cutoff = now - CLEANUP_INTERVAL
        self.users = {uid: t for uid, t in self.users.items() if t > cutoff}
        self._last_cleanup = now

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        now = time.monotonic()

        self._cleanup(now)

        last = self.users.get(user_id, 0)
        if now - last < self.rate_limit:
            logger.warning("Throttled user %s", user_id)
            await event.answer("⚠️ Не так быстро. Подожди секунду.")
            return

        self.users[user_id] = now
        return await handler(event, data)