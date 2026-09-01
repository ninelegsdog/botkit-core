"""Shared error handling for BotKit bots.

The per-bot error counter is resolved from :data:`botkit_core.metrics.ERRORS_TOTAL`,
set by the bot entrypoint via ``set_errors_counter``. Falls back to a no-op counter
if none was registered so the handler stays safe under any wiring order.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.types import TelegramObject

from botkit_core import metrics

logger = logging.getLogger(__name__)

# No-op counter used when a bot hasn't registered its real error counter yet.
_NOOP_COUNTER: Any = None


def _error_counter() -> Any:
    if metrics.ERRORS_TOTAL is not None:
        return metrics.ERRORS_TOTAL
    global _NOOP_COUNTER  # pylint: disable=global-statement
    if _NOOP_COUNTER is None:
        from prometheus_client import Counter

        _NOOP_COUNTER = Counter("botkit_errors_total_noop", "noop", ["error_type"])
    return _NOOP_COUNTER


async def default_error_handler(event: TelegramObject, exception: Exception) -> None:
    counter = _error_counter()
    if isinstance(exception, TelegramRetryAfter):
        counter.labels(error_type="retry_after").inc()
        logger.warning("TelegramRetryAfter: %s", exception)
        await asyncio.sleep(exception.retry_after)
        return
    if isinstance(exception, TelegramNetworkError):
        counter.labels(error_type="network").inc()
        logger.warning("TelegramNetworkError: %s", exception)
        return
    counter.labels(error_type="unhandled").inc()
    logger.critical("Unhandled error: %s", exception, exc_info=True)


def register_error_handler(dp: Any) -> None:
    @dp.error()  # type: ignore[untyped-decorator]
    async def _on_error(event: TelegramObject, exception: Exception) -> None:
        await default_error_handler(event, exception)


def setup_error_handling(dp: Any) -> None:
    """Convenience wrapper: point handler at dp and register it."""
    register_error_handler(dp)


class RetryMiddleware:
    """Retries handler execution on transient Telegram errors."""

    def __init__(self, max_retries: int = 3, delay: float = 1.0) -> None:
        self._max_retries = max_retries
        self._delay = delay

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        retries = 0
        while True:
            try:
                return await handler(event, data)
            except TelegramRetryAfter as exc:
                _error_counter().labels(error_type="retry_after").inc()
                retries += 1
                if retries >= self._max_retries:
                    raise
                logger.warning("RetryAfter in handler: %s", exc)
                await asyncio.sleep(exc.retry_after)
            except TelegramNetworkError as exc:
                _error_counter().labels(error_type="network").inc()
                retries += 1
                if retries >= self._max_retries:
                    raise
                logger.warning("NetworkError in handler (attempt %s): %s", retries, exc)
                await asyncio.sleep(self._delay * retries)
