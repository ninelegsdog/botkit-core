"""Tests for botkit_core.logging — JSON formatter + conversation_id."""
from __future__ import annotations

import io
import json
import logging

from botkit_core.logging import (
    ConversationContextFilter,
    get_conversation_id,
    get_json_formatter,
    set_bot_name,
    set_conversation_id,
    setup_logging,
)


def test_json_formatter_produces_json_with_fields() -> None:
    logger = logging.getLogger("test.json")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(get_json_formatter())
    handler.addFilter(ConversationContextFilter())
    logger.addHandler(handler)

    set_conversation_id("chat123")
    set_bot_name("testbot")
    logger.info("hello world")
    logger.handlers.clear()

    line = stream.getvalue().strip()
    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["conversation_id"] == "chat123"
    assert data["bot"] == "testbot"
    assert data["levelname"] == "INFO"


def test_conversation_context_filter_injects_defaults() -> None:
    set_conversation_id("-")
    set_bot_name("-")
    f = ConversationContextFilter()
    record = logging.LogRecord(name="x", level=logging.INFO, pathname="", lineno=0, msg="m", args=(), exc_info=None)
    assert f.filter(record) is True
    assert record.conversation_id == "-"  # type: ignore[attr-defined]
    assert record.bot == "-"  # type: ignore[attr-defined]


def test_setup_logging_json_and_plain() -> None:
    stream = io.StringIO()
    setup_logging(level="INFO", json=True, bot_name="mybot", stream=stream)
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert root.level == logging.INFO
    # plain mode should not raise
    stream2 = io.StringIO()
    setup_logging(level="INFO", json=False, bot_name="mybot", stream=stream2)
    assert len(logging.getLogger().handlers) == 1


def test_set_get_conversation_id() -> None:
    set_conversation_id("abc")
    assert get_conversation_id() == "abc"
    set_conversation_id("xyz")
    assert get_conversation_id() == "xyz"
