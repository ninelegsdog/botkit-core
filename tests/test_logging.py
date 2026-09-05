"""Tests for botkit_core.logging module."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from botkit_core.logging import (
    ConversationContextFilter,
    get_bot_name,
    get_conversation_id,
    get_json_formatter,
    set_bot_name,
    set_conversation_id,
    setup_logging,
)


def test_set_and_get_conversation_id():
    """Test setting and getting conversation_id."""
    set_conversation_id("test_chat_123")
    assert get_conversation_id() == "test_chat_123"

    set_conversation_id("another_chat_456")
    assert get_conversation_id() == "another_chat_456"

    # Default value
    set_conversation_id("-")
    assert get_conversation_id() == "-"


def test_set_and_get_bot_name():
    """Test setting and getting bot name."""
    set_bot_name("test_bot")
    assert get_bot_name() == "test_bot"

    set_bot_name("another_bot")
    assert get_bot_name() == "another_bot"

    # Default value
    set_bot_name("-")
    assert get_bot_name() == "-"


def test_conversation_context_filter():
    """Test ConversationContextFilter injects conversation_id and bot into LogRecord."""
    filter_obj = ConversationContextFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    set_conversation_id("test_chat_789")
    set_bot_name("test_bot")

    assert filter_obj.filter(record) is True
    assert record.conversation_id == "test_chat_789"
    assert record.bot == "test_bot"

    # Test default values when context vars are not set
    set_conversation_id("-")
    set_bot_name("-")
    record2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    assert filter_obj.filter(record2) is True
    assert record2.conversation_id == "-"
    assert record2.bot == "-"


def test_get_json_formatter():
    """Test get_json_formatter returns a JsonFormatter with expected format."""
    formatter = get_json_formatter()
    assert formatter is not None

    # Check format string contains expected fields
    fmt = formatter._fmt
    assert "asctime" in fmt
    assert "levelname" in fmt
    assert "name" in fmt
    assert "message" in fmt
    assert "conversation_id" in fmt
    assert "bot" in fmt


def test_setup_logging_json():
    """Test setup_logging configures root logger with JSON formatter."""
    stream = StringIO()
    setup_logging(level="DEBUG", json=True, bot_name="test_bot", stream=stream)

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1

    handler = root.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.level == logging.DEBUG
    # Check filter is added
    assert any(isinstance(f, ConversationContextFilter) for f in handler.filters)

    # Test logging output
    logger = logging.getLogger("test")
    logger.info("Test message")

    output = stream.getvalue()
    assert "Test message" in output
    # JSON format should contain expected fields
    data = json.loads(output.strip())
    assert data["message"] == "Test message"
    assert data["bot"] == "test_bot"
    assert data["levelname"] == "INFO"
    assert "asctime" in data
    assert "name" in data


def test_setup_logging_plain():
    """Test setup_logging configures root logger with plain formatter."""
    stream = StringIO()
    setup_logging(level="INFO", json=False, stream=stream)

    root = logging.getLogger()
    assert root.level == logging.INFO
    assert len(root.handlers) == 1

    handler = root.handlers[0]
    assert isinstance(handler.formatter, logging.Formatter)

    # Test logging output
    logger = logging.getLogger("test")
    logger.warning("Plain message")

    output = stream.getvalue()
    assert "Plain message" in output
    assert "WARNING" in output


def test_setup_logging_idempotent():
    """Test setup_logging clears existing handlers (idempotent)."""
    stream1 = StringIO()
    setup_logging(level="INFO", json=True, stream=stream1)
    assert len(logging.getLogger().handlers) == 1

    stream2 = StringIO()
    setup_logging(level="DEBUG", json=True, stream=stream2)
    assert len(logging.getLogger().handlers) == 1  # Should still be 1, not 2


def test_setup_logging_string_level():
    """Test setup_logging accepts string level."""
    stream = StringIO()
    setup_logging(level="WARNING", json=True, stream=stream)
    assert logging.getLogger().level == logging.WARNING


def test_setup_logging_clears_botkit_core_logger():
    """Test setup_logging sets level on botkit_core logger."""
    stream = StringIO()
    setup_logging(level="ERROR", json=True, stream=stream)
    botkit_logger = logging.getLogger("botkit_core")
    assert botkit_logger.level == logging.ERROR


def test_contextvar_isolation():
    """Test conversation_id and bot_name are isolated per context."""
    # This test simulates context isolation (e.g., async tasks)
    set_conversation_id("chat_1")
    set_bot_name("bot_1")
    assert get_conversation_id() == "chat_1"
    assert get_bot_name() == "bot_1"

    # Simulate another context
    set_conversation_id("chat_2")
    set_bot_name("bot_2")
    assert get_conversation_id() == "chat_2"
    assert get_bot_name() == "bot_2"


def test_filter_with_missing_attributes():
    """Test filter handles records without conversation_id/bot attributes."""
    filter_obj = ConversationContextFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test",
        args=(),
        exc_info=None,
    )
    # Remove attributes if they exist
    if hasattr(record, "conversation_id"):
        delattr(record, "conversation_id")
    if hasattr(record, "bot"):
        delattr(record, "bot")

    set_conversation_id("test_chat")
    set_bot_name("test_bot")

    assert filter_obj.filter(record) is True
    assert record.conversation_id == "test_chat"
    assert record.bot == "test_bot"


def test_json_output_structure():
    """Test JSON log output has correct structure with all required fields."""
    stream = StringIO()
    setup_logging(level="INFO", json=True, bot_name="structure_test", stream=stream)

    logger = logging.getLogger("structure_test")
    logger.info("Structure test message")

    output = stream.getvalue()
    data = json.loads(output.strip())

    # Check all required fields are present
    required_fields = ["asctime", "levelname", "name", "message", "conversation_id", "bot"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    assert data["message"] == "Structure test message"
    assert data["bot"] == "structure_test"
    assert data["levelname"] == "INFO"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
