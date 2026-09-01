# botkit-core

Shared core library for the 9 BotKit Telegram bots (bookingbot, delivery,
docuflow, leadgen, membership, pricesentry, reminder, store, support).

**Version:** 0.1.0 — the extractable shared surface, published to GHCR.

## Modules
| Module | Purpose |
|--------|---------|
| `botkit_core.metrics` | Prometheus skeleton: `bot_updates_total`, `UpdatesMiddleware`, `health`/`metrics`/`create_metrics_app`/`start_metrics_server`, `set_errors_counter`, `BaseMetrics` |
| `botkit_core.errors` | `default_error_handler`, `register_error_handler`, `RetryMiddleware` — error counter resolved via `metrics.ERRORS_TOTAL` (no-op fallback) |
| `botkit_core.sentry` | Lazy `init_sentry(dsn)` |
| `botkit_core.webhook` | `build_webhook_app` (aiohttp + aiogram) |

## Design notes
- The per-bot copies of `src/core` have **diverged** (3 generations: modern
  AppState, legacy AdminGate, reminder). v0.1.0 extracts only the
  byte-identical / parameterizable surface and wires per-bot divergence via
  injection (`set_errors_counter`) rather than duplication.
- Bots are migrated one at a time; each keeps its own `src/core` as a shim
  until the shared import is fully adopted (rollback-safe).

## Dev
```
pip install -e ".[dev]"
ruff check .
mypy botkit_core/
pytest -q            # 82%+ coverage gate
```
