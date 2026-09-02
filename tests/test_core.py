"""Tests for botkit_core core modules — metrics, errors, webhook, sentry."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError

from botkit_core import errors, metrics, sentry, webhook


def test_version() -> None:
    import botkit_core

    assert botkit_core.__version__ == "0.4.0"


def test_sentry_lazy_noop_no_dsn() -> None:
    sentry.init_sentry(None)


def test_sentry_init_with_dsn_missing_pkg(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(name, *a, **k):
        raise ImportError("no sentry_sdk")

    monkeypatch.setitem(__import__("builtins").__dict__, "__import__", fake_import)
    sentry.init_sentry("https://x@sentry.io/1")


def test_errors_counter_returns_shared() -> None:
    counter = errors._error_counter()
    counter.labels(error_type="unhandled").inc()
    assert counter is metrics.BOTKIT_ERRORS_TOTAL


class FakeEvent:
    pass


def test_updates_middleware_counts_with_event() -> None:
    async def handler(event, data):
        return "ok"

    mw = metrics.UpdatesMiddleware()
    asyncio.run(mw(handler, FakeEvent(), {}))
    sample = metrics.BOTKIT_UPDATES_TOTAL.labels(type="fakeevent")._value.get()
    assert sample >= 1


def test_errors_default_handler_network() -> None:
    before = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="network")._value.get()

    async def run() -> None:
        await errors.default_error_handler(None, TelegramNetworkError(message="net", method="getUpdates"))

    asyncio.run(run())
    after = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="network")._value.get()
    assert after == before + 1


def test_errors_default_handler_unhandled() -> None:
    before = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="unhandled")._value.get()

    async def run() -> None:
        await errors.default_error_handler(None, ValueError("boom"))

    asyncio.run(run())
    after = metrics.BOTKIT_ERRORS_TOTAL.labels(error_type="unhandled")._value.get()
    assert after == before + 1


async def test_metrics_and_health_endpoints(aiohttp_client: Any) -> None:
    app = metrics.create_metrics_app()
    client = await aiohttp_client(app)
    resp = await client.get("/metrics")
    assert resp.status == 200
    body = await resp.text()
    assert "botkit_updates_total" in body
    assert "botkit_errors_total" in body
    assert "botkit_handler_duration_seconds_bucket" in body
    resp = await client.get("/health")
    assert (await resp.text()) == "ok"


def test_build_webhook_app_returns_aiohttp_app() -> None:
    bot = Bot(token="123456:TESTTOKEN", session=None)
    dp = Dispatcher()
    app = webhook.build_webhook_app(dp, bot, "secret")
    from aiohttp import web

    assert isinstance(app, web.Application)
