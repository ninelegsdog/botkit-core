"""Shared RED metrics for all BotKit bots.

Exposes the common update/error counters and the aiohttp metrics/health
endpoints. Per-bot domain counters are registered by the bot's own code.
``start_metrics_server`` keeps the same surface across all bots.

Metric prefix: ``botkit_`` — aligned with the Grafana dashboard queries.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

logger = logging.getLogger(__name__)

# ── RED metrics (default registry, prefix botkit_) ──────

BOTKIT_UPDATES_TOTAL = Counter(
    "botkit_updates_total",
    "Total updates received from Telegram",
    ["type"],
)

BOTKIT_ERRORS_TOTAL = Counter(
    "botkit_errors_total",
    "Total errors handled by the global error handler",
    ["error_type"],
)

BOTKIT_HANDLER_DURATION = Histogram(
    "botkit_handler_duration_seconds",
    "Handler execution time in seconds",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

BOTKIT_WEBHOOK_DURATION = Histogram(
    "botkit_webhook_duration_seconds",
    "Webhook HTTP request processing time",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Backward-compat alias used by errors.py and bot entrypoints.
ERRORS_TOTAL: Counter = BOTKIT_ERRORS_TOTAL


# ── Middleware ────────────────────────────────────────────

class UpdatesMiddleware:
    """Counts every incoming update and records handler duration."""

    async def __call__(self, handler: Any, event: Any, data: dict[str, Any]) -> Any:
        BOTKIT_UPDATES_TOTAL.labels(type=type(event).__name__.lower()).inc()
        start = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            BOTKIT_HANDLER_DURATION.observe(time.perf_counter() - start)


# ── Health + metrics endpoints ───────────────────────────

async def health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def metrics(request: web.Request) -> web.Response:
    return web.Response(
        body=generate_latest(),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


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
