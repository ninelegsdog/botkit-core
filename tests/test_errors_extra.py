from __future__ import annotations

import asyncio

import pytest
from aiogram.exceptions import TelegramNetworkError
from prometheus_client import Counter

from botkit_core import errors, metrics


def test_set_errors_counter_sets_global() -> None:
    c = Counter("test_set_counter", "test", ["error_type"])
    metrics.set_errors_counter(c)
    assert metrics.ERRORS_TOTAL is c
    metrics.ERRORS_TOTAL = None


def test_retry_middleware_success() -> None:
    async def handler(event, data):
        return "ok"

    mw = errors.RetryMiddleware(max_retries=3, delay=0)
    result = asyncio.run(mw(handler, None, {}))
    assert result == "ok"


def test_retry_middleware_retries_network() -> None:
    calls = {"n": 0}

    async def handler(event, data):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TelegramNetworkError(message="net", method="getUpdates")
        return "ok"

    mw = errors.RetryMiddleware(max_retries=3, delay=0)
    result = asyncio.run(mw(handler, None, {}))
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_middleware_gives_up() -> None:
    async def handler(event, data):
        raise TelegramNetworkError(message="net", method="getUpdates")

    mw = errors.RetryMiddleware(max_retries=2, delay=0)
    with pytest.raises(TelegramNetworkError):
        asyncio.run(mw(handler, None, {}))
