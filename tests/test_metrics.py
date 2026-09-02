"""Tests for botkit_core.metrics — RED metrics + aiohttp endpoints."""
from __future__ import annotations

import asyncio
from typing import Any


from botkit_core import metrics


class FakeEvent:
    pass


def test_version() -> None:
    import botkit_core

    assert botkit_core.__version__ == "0.1.0"


def test_botkit_updates_total_counter() -> None:
    before = metrics.BOTKIT_UPDATES_TOTAL.labels(type="fakeevent")._value.get()
    mw = metrics.UpdatesMiddleware()

    async def handler(event, data):
        return "ok"

    asyncio.run(mw(handler, FakeEvent(), {}))
    after = metrics.BOTKIT_UPDATES_TOTAL.labels(type="fakeevent")._value.get()
    assert after == before + 1


def test_botkit_handler_duration_histogram() -> None:
    mw = metrics.UpdatesMiddleware()

    async def slow_handler(event, data):
        await asyncio.sleep(0.01)
        return "ok"

    asyncio.run(mw(slow_handler, FakeEvent(), {}))
    assert metrics.BOTKIT_HANDLER_DURATION._sum.get() >= 0.01


def test_botkit_errors_total_counter() -> None:
    before = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="test")._value.get()
    metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="test").inc()
    after = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="test")._value.get()
    assert after == before + 1


def test_errors_total_alias_is_same_counter() -> None:
    assert metrics.ERRORS_TOTAL is metrics.BOTKIT_ERRORS_TOTAL


async def test_metrics_and_health_endpoints(aiohttp_client: Any) -> None:
    app = metrics.create_metrics_app()
    client = await aiohttp_client(app)
    resp = await client.get("/metrics")
    assert resp.status == 200
    body = await resp.text()
    assert "botkit_updates_total" in body
    assert "botkit_errors_total" in body
    assert "botkit_handler_duration_seconds_bucket" in body
    assert "botkit_webhook_duration_seconds_bucket" in body
    resp = await client.get("/health")
    assert (await resp.text()) == "ok"
