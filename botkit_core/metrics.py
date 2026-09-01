"""Shared Prometheus metrics skeleton for BotKit bots.

Exposes the common update/error counters and the aiohttp metrics/health
endpoints. Extra per-bot counters are registered by the bot's own code via
``register_*`` helpers, and ``start_metrics_server`` keeps the same surface
across all bots.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

logger = logging.getLogger(__name__)


UPDATES_TOTAL = Counter("bot_updates_total", "Total updates received from Telegram", ["type"])

# Set by each bot's entrypoint to enable error accounting (name is bot-specific,
# e.g. botkit_membership uses ERRORS_TOTAL). Kept as a variable so the shared
# error handler can increment whatever counter the bot registers.
ERRORS_TOTAL: Counter | None = None


def set_errors_counter(counter: Counter) -> None:
    """Point the shared error handler at a bot-specific error counter."""
    global ERRORS_TOTAL  # pylint: disable=global-statement
    ERRORS_TOTAL = counter


class UpdatesMiddleware:
    """Counts every incoming update."""

    async def __call__(self, handler: Any, event: Any, data: dict[str, Any]) -> Any:
        UPDATES_TOTAL.labels(type=type(event).__name__.lower()).inc()
        return await handler(event, data)


@dataclass
class BaseMetrics:
    """Common uptime/message counters. Extend per bot for domain metrics."""
    _start: float = field(default_factory=time.time)
    messages_processed: int = 0
    errors: int = 0

    def inc_messages(self) -> None:
        self.messages_processed += 1

    def inc_errors(self) -> None:
        self.errors += 1

    def uptime_seconds(self) -> float:
        return time.time() - self._start


async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def metrics(request: web.Request) -> web.Response:
    return web.Response(body=generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


def create_metrics_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    return app


async def start_metrics_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_metrics_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Metrics server started on port %s", port)
    return runner
