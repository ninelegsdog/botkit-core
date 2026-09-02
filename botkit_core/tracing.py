"""Distributed tracing for BotKit using OpenTelemetry.

Provides OTLP tracer setup and aiogram middleware for automatic span creation.
"""
from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ── ContextVar for current span ─────────────────────────

_current_span_ctx: contextvars.ContextVar[trace.Span | None] = contextvars.ContextVar(
    "current_span", default=None
)


def get_current_span() -> trace.Span | None:
    """Get the current active span from context."""
    return _current_span_ctx.get()


def set_current_span(span: trace.Span | None) -> None:
    """Set the current active span in context."""
    _current_span_ctx.set(span)


# ── Tracer setup ────────────────────────────────────────

def setup_tracing(
    service_name: str,
    *,
    otlp_endpoint: str = "http://127.0.0.1:4318/v1/traces",
    sample_rate: float = 1.0,
) -> trace.Tracer:
    """Configure OpenTelemetry tracer with OTLP HTTP exporter.

    Args:
        service_name: Service name for resource attributes (e.g., "bookingbot").
        otlp_endpoint: OTLP HTTP endpoint (default: collector on localhost:4318).
        sample_rate: Trace sampling rate 0.0-1.0 (default: 1.0 = all).

    Returns:
        Tracer instance for manual instrumentation.
    """
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    # Auto-instrument aiohttp client/server if available
    try:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
        AioHttpClientInstrumentor().instrument()
    except Exception:
        pass  # optional

    return trace.get_tracer(service_name)


# ── Aiogram middleware ──────────────────────────────────

class TracingMiddleware(BaseMiddleware):
    """Creates a span per incoming Telegram update."""

    def __init__(self, tracer: trace.Tracer | None = None) -> None:
        self._tracer = tracer or trace.get_tracer(__name__)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract context from event (if propagated via headers - not typical for Telegram)
        # For now, start a new trace per update
        update_id = getattr(event, "update_id", "unknown")
        event_type = type(event).__name__

        with self._tracer.start_as_current_span(
            f"botkit.update.{event_type}",
            kind=trace.SpanKind.SERVER,
            attributes={
                "botkit.update_id": update_id,
                "botkit.event_type": event_type,
            },
        ) as span:
            set_current_span(span)
            try:
                result = await handler(event, data)
                span.set_status(trace.Status(trace.StatusCode.OK))
                return result
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
                raise
            finally:
                set_current_span(None)


__all__ = [
    "TracingMiddleware",
    "get_current_span",
    "set_current_span",
    "setup_tracing",
]
