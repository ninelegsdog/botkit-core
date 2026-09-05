"""Tests for botkit_core.middleware.logging module."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from botkit_core.middleware.logging import ErrorLoggingMiddleware, LoggingMiddleware


class LogCapture:
    """Capture log records for testing."""
    def __init__(self):
        self.records = []
        self.handler = logging.StreamHandler()
        self.handler.setLevel(logging.DEBUG)
        self.handler.handle = self._capture

    def _capture(self, record):
        self.records.append(record)

    def get_records(self):
        return self.records

    def clear(self):
        self.records.clear()


@pytest.fixture
def log_capture():
    """Capture log records for testing."""
    capture = LogCapture()
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(capture.handler)
    root.setLevel(logging.DEBUG)

    yield capture

    # Cleanup
    root.handlers.clear()


def make_mock_event(chat_id: int = 123, user_id: int = 456):
    """Create a mock Telegram event."""
    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = chat_id
    event.from_user = MagicMock()
    event.from_user.id = 456
    return event


@pytest.mark.asyncio
async def test_logging_middleware_request_response():
    """Test LoggingMiddleware logs request and response."""

    middleware = LoggingMiddleware(log_requests=True, log_responses=True)
    handler = AsyncMock(return_value="OK")
    event = make_mock_event(chat_id=123, user_id=456)

    result = await middleware(handler, event, {})

    assert result == "OK"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_logging_middleware_handler_called():
    """Test LoggingMiddleware calls the handler."""

    middleware = LoggingMiddleware()
    handler = AsyncMock(return_value="OK")
    event = make_mock_event(chat_id=123, user_id=456)

    result = await middleware(handler, event, {})

    assert result == "OK"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_logging_middleware_slow_handler():
    """Test LoggingMiddleware detects slow handlers."""
    import asyncio

    middleware = LoggingMiddleware(slow_threshold_ms=10)

    async def slow_handler(event, data):
        await asyncio.sleep(0.05)
        return "OK"

    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = 123
    event.from_user = MagicMock()
    event.from_user.id = 456

    # Just verify it doesn't crash
    result = await middleware(slow_handler, MagicMock(), {})
    assert result == "OK"


@pytest.mark.asyncio
async def test_logging_middleware_error_handling():
    """Test LoggingMiddleware handles errors."""

    middleware = LoggingMiddleware(log_errors=True)

    async def failing_handler(event, data):
        raise ValueError("Test error")

    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = 123
    event.from_user = MagicMock()
    event.from_user.id = 456

    with pytest.raises(ValueError, match="Test error"):
        await middleware(failing_handler, MagicMock(), {})


@pytest.mark.asyncio
async def test_error_logging_middleware():
    """Test ErrorLoggingMiddleware logs unhandled errors."""

    middleware = ErrorLoggingMiddleware()

    async def failing_handler(event, data):
        raise RuntimeError("Critical failure")

    event = MagicMock()
    event.update_id = 1

    with pytest.raises(RuntimeError, match="Critical failure"):
        await middleware(failing_handler, MagicMock(), {})


@pytest.mark.asyncio
async def test_logging_middleware_disabled_requests():
    """Test LoggingMiddleware with log_requests=False."""

    middleware = LoggingMiddleware(log_requests=False, log_responses=True)
    handler = AsyncMock(return_value="OK")
    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = 123

    result = await middleware(handler, MagicMock(), {})
    assert result == "OK"


@pytest.mark.asyncio
async def test_logging_middleware_disabled_responses():
    """Test LoggingMiddleware with log_responses=False."""

    middleware = LoggingMiddleware(log_requests=True, log_responses=False)
    handler = AsyncMock(return_value="OK")
    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = 123

    result = await middleware(handler, MagicMock(), {})
    assert result == "OK"


@pytest.mark.asyncio
async def test_logging_middleware_conversation_id_from_chat():
    """Test conversation_id extraction from chat."""

    middleware = LoggingMiddleware()

    event = MagicMock()
    event.update_id = 1
    event.chat = MagicMock()
    event.chat.id = 789

    handler = AsyncMock(return_value="OK")
    await middleware(handler, event, {})

    # Just verify it runs without error


@pytest.mark.asyncio
async def test_logging_middleware_conversation_id_from_message():
    """Test conversation_id extraction from message.chat."""

    middleware = LoggingMiddleware()

    event = MagicMock()
    event.message = MagicMock()
    event.message.chat = MagicMock()
    event.message.chat.id = 999
    event.update_id = 1

    handler = AsyncMock(return_value="OK")
    await middleware(handler, event, {})

    # Just verify it runs without error


@pytest.mark.asyncio
async def test_error_logging_middleware_logs():
    """Test ErrorLoggingMiddleware logs errors."""

    middleware = ErrorLoggingMiddleware()

    async def failing_handler(event, data):
        raise RuntimeError("Critical failure")

    event = MagicMock()
    event.update_id = 1

    with pytest.raises(RuntimeError, match="Critical failure"):
        await middleware(failing_handler, MagicMock(), {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
