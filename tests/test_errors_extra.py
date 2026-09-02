"""Extended error handler and retry middleware tests."""
from __future__ import annotations

import asyncio

import pytest
from aiogram.exceptions import TelegramNetworkError

from botkit_core import errors, metrics


def test_errors_total_is_always_set() -> None:
    assert metrics.ERRORS_TOTAL is not None
    assert metrics.ERRORS_TOTAL is metrics.BOTKIT_ERRORS_TOTAL


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
