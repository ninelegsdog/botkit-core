from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError
from prometheus_client import Counter

from botkit_core import errors, metrics, sentry, webhook


def test_version() -> None:
    import botkit_core

    assert botkit_core.__version__ == "0.1.0"


def test_sentry_lazy_noop_no_dsn() -> None:
    sentry.init_sentry(None)


def test_sentry_init_with_dsn_missing_pkg(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(name, *a, **k):
        raise ImportError("no sentry_sdk")

    monkeypatch.setitem(__import__("builtins").__dict__, "__import__", fake_import)
    sentry.init_sentry("https://x@sentry.io/1")


def test_errors_counter_fallback_increments() -> None:
    metrics.ERRORS_TOTAL = None
    counter = errors._error_counter()
    counter.labels(error_type="unhandled").inc()
    assert counter.labels(error_type="unhandled")._value.get() >= 1


def test_errors_counter_uses_registered() -> None:
    c = Counter("test_errors", "test", ["error_type"])
    metrics.ERRORS_TOTAL = c
    assert errors._error_counter() is c


class FakeEvent:
    pass


def test_updates_middleware_counts_with_event() -> None:
    async def handler(event, data):
        return "ok"

    mw = metrics.UpdatesMiddleware()
    asyncio.run(mw(handler, FakeEvent(), {}))
    sample = metrics.UPDATES_TOTAL.labels(type="fakeevent")._value.get()
    assert sample == 1


def test_errors_default_handler_network(monkeypatch: pytest.MonkeyPatch) -> None:
    c = Counter("test_errors_handler", "test", ["error_type"])
    metrics.ERRORS_TOTAL = c

    async def run() -> None:
        await errors.default_error_handler(None, TelegramNetworkError(message="net", method="getUpdates"))

    asyncio.run(run())
    assert c.labels(error_type="network")._value.get() == 1


def test_errors_default_handler_unhandled(monkeypatch: pytest.MonkeyPatch) -> None:
    c = Counter("test_errors_unhandled", "test", ["error_type"])
    metrics.ERRORS_TOTAL = c

    async def run() -> None:
        await errors.default_error_handler(None, ValueError("boom"))

    asyncio.run(run())
    assert c.labels(error_type="unhandled")._value.get() == 1


async def test_metrics_and_health_endpoints(aiohttp_client: Any) -> None:
    app = metrics.create_metrics_app()
    client = await aiohttp_client(app)
    resp = await client.get("/metrics")
    assert resp.status == 200
    body = await resp.text()
    assert "bot_updates_total" in body
    resp = await client.get("/health")
    assert (await resp.text()) == "ok"


def test_build_webhook_app_returns_aiohttp_app() -> None:
    bot = Bot(token="123456:TESTTOKEN", session=None)
    dp = Dispatcher()
    app = webhook.build_webhook_app(dp, bot, "secret")
    from aiohttp import web

    assert isinstance(app, web.Application)


def test_base_metrics_uptime() -> None:
    m = metrics.BaseMetrics()
    m.inc_messages()
    m.inc_errors()
    assert m.messages_processed == 1
    assert m.errors == 1
    assert m.uptime_seconds() >= 0
