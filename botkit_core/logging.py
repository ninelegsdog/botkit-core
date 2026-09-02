"""Structured JSON logging for BotKit.

Provides JSON formatter (python-json-logger) + ContextVar for conversation_id.
Usage:
    from botkit_core.logging import setup_logging, set_conversation_id, ConversationContextFilter

    setup_logging(level="INFO", json=True, bot_name="bookingbot")
    # in aiogram middleware:
    set_conversation_id(str(event.message.chat.id) if event.message else "unknown")
"""
from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any

try:
    from pythonjsonlogger.json import JsonFormatter  # type: ignore[import-not-found, import-untyped]

    _has_json = True
except ImportError:
    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import-not-found, import-untyped]

        JsonFormatter = jsonlogger.JsonFormatter  # type: ignore[attr-defined]
        _has_json = True
    except ImportError:
        JsonFormatter = None  # type: ignore[assignment]
        _has_json = False

# ── ContextVar for conversation_id ──────────────────

_conversation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "conversation_id", default="-"
)
_bot_name_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("bot_name", default="-")


def set_conversation_id(value: str) -> None:
    """Set conversation_id for current context (e.g. chat_id)."""
    _conversation_id_ctx.set(value)


def get_conversation_id() -> str:
    return _conversation_id_ctx.get()


def set_bot_name(value: str) -> None:
    _bot_name_ctx.set(value)


def get_bot_name() -> str:
    return _bot_name_ctx.get()


class ConversationContextFilter(logging.Filter):
    """Injects conversation_id and bot into LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "conversation_id"):
            setattr(record, "conversation_id", _conversation_id_ctx.get())
        if not hasattr(record, "bot"):
            setattr(record, "bot", _bot_name_ctx.get())
        return True


def get_json_formatter() -> logging.Formatter:
    """Return JsonFormatter with standard fields."""
    if not _has_json or JsonFormatter is None:
        raise RuntimeError("python-json-logger is not installed; add python-json-logger>=2.0 to dependencies")
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s %(conversation_id)s %(bot)s"
    return JsonFormatter(fmt)  # type: ignore[no-any-return]


def setup_logging(
    level: int | str = "INFO",
    *,
    json: bool = True,
    bot_name: str | None = None,
    stream: Any = None,
) -> None:
    """Configure root logger with JSON or plain formatter.

    Idempotent: clears existing handlers before adding new one.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    if bot_name is not None:
        set_bot_name(bot_name)

    root = logging.getLogger()
    root.setLevel(level)
    # Clear existing handlers to avoid duplicate logs in tests/reload
    root.handlers.clear()

    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setLevel(level)
    handler.addFilter(ConversationContextFilter())
    if json:
        handler.setFormatter(get_json_formatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root.addHandler(handler)
    # Ensure botkit loggers propagate
    logging.getLogger("botkit_core").setLevel(level)
