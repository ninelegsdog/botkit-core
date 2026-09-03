"""Tests for botkit_core.tracing."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from botkit_core.tracing import (
    TracingMiddleware,
    get_current_span,
    set_current_span,
    setup_tracing,
)


def test_get_set_current_span() -> None:
    assert get_current_span() is None
    mock_span = MagicMock()
    set_current_span(mock_span)
    assert get_current_span() is mock_span
    set_current_span(None)
    assert get_current_span() is None


@patch("botkit_core.tracing.trace.get_tracer")
@patch("botkit_core.tracing.trace.set_tracer_provider")
@patch("botkit_core.tracing.OTLPSpanExporter")
@patch("botkit_core.tracing.BatchSpanProcessor")
@patch("botkit_core.tracing.TracerProvider")
def test_setup_tracing_creates_provider(
    mock_provider_class,
    mock_processor_class,
    mock_exporter_class,
    mock_set_provider,
    mock_get_tracer,
) -> None:
    mock_provider = MagicMock()
    mock_provider_class.return_value = mock_provider
    mock_tracer = MagicMock()
    mock_get_tracer.return_value = mock_tracer

    tracer = setup_tracing("test-bot", otlp_endpoint="http://localhost:4318/v1/traces")

    mock_provider_class.assert_called_once()
    mock_exporter_class.assert_called_once_with(endpoint="http://localhost:4318/v1/traces")
    mock_processor_class.assert_called_once()
    mock_provider.add_span_processor.assert_called_once()
    mock_set_provider.assert_called_once_with(mock_provider)
    assert tracer is mock_tracer
    mock_get_tracer.assert_called_once_with("test-bot")


@patch("botkit_core.tracing.trace.get_tracer")
@patch("botkit_core.tracing.trace.set_tracer_provider")
@patch("botkit_core.tracing.OTLPSpanExporter")
@patch("botkit_core.tracing.BatchSpanProcessor")
@patch("botkit_core.tracing.TracerProvider")
def test_setup_tracing_default_endpoint(
    mock_provider_class,
    mock_processor_class,
    mock_exporter_class,
    mock_set_provider,
    mock_get_tracer,
) -> None:
    mock_provider = MagicMock()
    mock_provider_class.return_value = mock_provider
    mock_get_tracer.return_value = MagicMock()

    setup_tracing("test-bot")

    mock_exporter_class.assert_called_once_with(endpoint="http://127.0.0.1:4318/v1/traces")


# Simple event class for testing (avoids pydantic validation)
class FakeEvent:
    def __init__(self, update_id: int, event_type: str = "Message"):
        self.update_id = update_id
        self._type = event_type




@pytest.mark.asyncio
async def test_tracing_middleware_creates_span() -> None:
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_tracer.start_as_current_span.return_value = mock_span

    mw = TracingMiddleware(tracer=mock_tracer)

    # Simple object with update_id attribute
    class Event:
        update_id = 123
        __class__ = type("Message", (), {"__name__": "Message"})

    event = Event()
    data = {}

    async def handler(ev, dt):
        return "result"

    result = await mw(handler, event, data)

    assert result == "result"
    mock_tracer.start_as_current_span.assert_called_once()
    call_kwargs = mock_tracer.start_as_current_span.call_args[1]
    assert call_kwargs["kind"] is not None
    assert "botkit.update_id" in call_kwargs["attributes"]
    assert call_kwargs["attributes"]["botkit.update_id"] == 123
    mock_span.set_status.assert_called()
    mock_span.__enter__.assert_called_once()
    mock_span.__exit__.assert_called_once()


@pytest.mark.asyncio
async def test_tracing_middleware_records_exception() -> None:
    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_tracer.start_as_current_span.return_value = mock_span

    mw = TracingMiddleware(tracer=mock_tracer)

    class Event:
        update_id = 456
        __class__ = type("CallbackQuery", (), {"__name__": "CallbackQuery"})

    event = Event()
    data = {}

    async def handler(ev, dt):
        raise ValueError("test error")

    with pytest.raises(ValueError, match="test error"):
        await mw(handler, event, data)

    mock_span.record_exception.assert_called_once()
    mock_span.set_status.assert_called()
    status_call = mock_span.set_status.call_args[0][0]
    assert status_call.status_code.name == "ERROR"


@pytest.mark.asyncio
async def test_tracing_middleware_without_tracer() -> None:
    """Test middleware works with default tracer."""
    with patch("botkit_core.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = MagicMock(return_value=mock_span)
        mock_span.__exit__ = MagicMock(return_value=False)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        mw = TracingMiddleware()  # no tracer passed

        class Event:
            update_id = 789
            __class__ = type("Update", (), {"__name__": "Update"})

        event = Event()
        data = {}

        async def handler(ev, dt):
            return "ok"

        result = await mw(handler, event, data)

        assert result == "ok"
        mock_get_tracer.assert_called_once()
