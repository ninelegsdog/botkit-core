"""Request/response logging middleware for BotKit.

Provides structured logging for:
- Request/response lifecycle
- Error handling
- Latency tracking
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.types import TelegramObject

from botkit_core.logging import get_conversation_id, set_conversation_id

logger = logging.getLogger("botkit_core.middleware.logging")


class LoggingMiddleware:
    """Middleware for logging request/response lifecycle with latency tracking.

    Logs:
    - Incoming update (type, conversation_id)
    - Handler latency
    - Errors with traceback
    - Response status
    """

    def __init__(
        self,
        *,
        log_requests: bool = True,
        log_responses: bool = True,
        log_errors: bool = True,
        slow_threshold_ms: int = 1000,
    ) -> None:
        """
        Args:
            log_requests: Log incoming updates
            log_responses: Log successful responses
            log_errors: Log handler errors
            slow_threshold_ms: Threshold in ms for slow handler warning
        """
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.log_errors = log_errors
        self.slow_threshold_ms = slow_threshold_ms

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Process the event with logging."""
        # Extract conversation_id from update
        conversation_id = self._extract_conversation_id(event)
        set_conversation_id(conversation_id)

        update_type = type(event).__name__
        update_id = getattr(event, "update_id", "unknown")

        if self.log_requests:
            logger.info(
                "Incoming update",
                extra={
                    "update_type": update_type,
                    "update_id": update_id,
                    "conversation_id": conversation_id,
                },
            )

        start_time = time.perf_counter()
        try:
            result = await handler(event, data)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if self.log_responses:
                logger.info(
                    "Handler completed",
                    extra={
                        "update_type": type(event).__name__,
                        "latency_ms": round(elapsed_ms, 2),
                        "conversation_id": get_conversation_id(),
                    },
                )

            # Log slow handlers
            if elapsed_ms > self.slow_threshold_ms:
                logger.warning(
                    "Slow handler detected",
                    extra={
                        "update_type": type(event).__name__,
                        "latency_ms": round(elapsed_ms, 2),
                        "threshold_ms": self.slow_threshold_ms,
                        "conversation_id": get_conversation_id(),
                    },
                )

            return result

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            if self.log_errors:
                logger.exception(
                    "Handler error",
                    extra={
                        "update_type": type(event).__name__,
                        "latency_ms": round(elapsed_ms, 2),
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "conversation_id": get_conversation_id(),
                    },
                )
            raise

    def _extract_conversation_id(self, event: Any) -> str:
        """Extract conversation_id from various update types."""
        # Try chat first (messages, callback queries)
        if hasattr(event, "chat") and event.chat is not None:
            return str(event.chat.id)

        # Try from_user (private messages)
        if hasattr(event, "from_user") and event.from_user is not None:
            return str(event.from_user.id)

        # For callback queries, try message.chat
        if (
            hasattr(event, "message")
            and event.message is not None
            and event.message.chat is not None
        ):
            return str(event.message.chat.id)

        return "-"


class ErrorLoggingMiddleware:
    """Middleware specifically for error logging with full traceback."""

    def __init__(self, logger_name: str = "botkit_core.errors") -> None:
        self.logger = logging.getLogger(logger_name)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            self.logger.exception(
                "Unhandled error in handler",
                extra={
                    "update_type": type(event).__name__,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            raise


__all__ = ["LoggingMiddleware", "ErrorLoggingMiddleware"]
