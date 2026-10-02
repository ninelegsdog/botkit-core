# botkit-core

Shared core library for the BotKit Telegram bots — the common surface that would otherwise be
duplicated in every project: payments, metrics, errors, logging, tracing, Sentry and the
aiohttp webhook app.

**Version: 0.8.2** · Python 3.12+ · aiogram 3.30+ · MIT

Currently used by 9 production bots:
[bookingbot](https://github.com/ninelegsdog/botkit-bookingbot) ·
[delivery](https://github.com/ninelegsdog/botkit-delivery) ·
[docuflow](https://github.com/ninelegsdog/botkit-docuflow) ·
[leadgen](https://github.com/ninelegsdog/botkit-leadgen) ·
[membership](https://github.com/ninelegsdog/botkit-membership) ·
[pricesentry](https://github.com/ninelegsdog/botkit-pricesentry) ·
[reminder](https://github.com/ninelegsdog/botkit-reminder) ·
[store](https://github.com/ninelegsdog/botkit-store) ·
[support](https://github.com/ninelegsdog/botkit-support)

---

## Why this library exists

The nine bots grew independently and carried three generations of their own `src/core`.
Rather than forcing a big-bang migration, this package extracts only the byte-identical or
parameterizable surface, and wires the per-bot divergence through **injection** rather than
duplication — for example, the error counter is supplied via `set_errors_counter`.

Each bot keeps its own `src/core` shim re-exporting from this package, so a bot can be rolled
back to its local copy without a code change. That is why the migration is safe to do one bot
at a time.

## Install

```bash
# pinned to the tag the bots use
pip install "botkit-core @ git+https://github.com/ninelegsdog/botkit-core.git@v0.8.2"
```

For development:

```bash
git clone https://github.com/ninelegsdog/botkit-core.git
cd botkit-core
pip install -e ".[dev]"
```

## Modules

| Module | Purpose |
|--------|---------|
| `botkit_core.payments` | `PaymentProvider` protocol + `YooKassaPaymentProvider` (ЮKassa), Telegram Stars (XTR) and `MockPaymentProvider` for tests; `create_payment_provider(name, **kwargs)` factory |
| `botkit_core.metrics` | Prometheus skeleton: `bot_updates_total`, `ERRORS_TOTAL`, `UpdatesMiddleware`, `health` / `version` / `create_metrics_app` / `start_metrics_server`, `set_errors_counter`, `BaseMetrics` |
| `botkit_core.errors` | `default_error_handler`, `register_error_handler`, `RetryMiddleware`; the error counter is resolved through `metrics.ERRORS_TOTAL` with a no-op fallback |
| `botkit_core.logging` | Structured JSON logging via `python-json-logger` |
| `botkit_core.middleware.logging` | aiohttp request/response logging middleware |
| `botkit_core.tracing` | OpenTelemetry OTLP tracer setup; honours `OTEL_EXPORTER_OTLP_ENDPOINT` |
| `botkit_core.sentry` | Lazy `init_sentry(dsn)` — no import-time cost when Sentry is not used |
| `botkit_core.webhook` | `build_webhook_app` — aiohttp + aiogram webhook application |

## Quickstart

```python
from botkit_core.metrics import create_metrics_app, set_errors_counter
from botkit_core.payments import create_payment_provider
from botkit_core.webhook import build_webhook_app

# payments: "yookassa" | "stars" | "mock"
payments = create_payment_provider("yookassa", shop_id=..., secret_key=...)

# errors counter must be injected so errors.py and metrics.py agree
set_errors_counter(...)  # see signature in botkit_core.metrics

app = build_webhook_app(dp)   # aiohttp app with /webhook, /health, /metrics
```

Every module is import-safe and side-effect-free at import time — nothing here opens a
connection or reads secrets until you call it.

## Configuration

The library itself reads only two environment variables, and both are optional:

| Variable | Meaning |
|---|---|
| `BUILD_SHA` | Commit SHA exposed via `/health` and `/version`, so a running container can be traced back to a commit |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint for `tracing.py` |

Secrets (bot tokens, ЮKassa keys, Sentry DSN) are supplied by the calling bot, never read here.
See `.env.example`.

## Development

```bash
pip install -e ".[dev]"
ruff check .
mypy botkit_core/
pytest -q
```

CI runs lint → type check → tests on every push and pull request.
**Test coverage: 81 % measured, gate 70 %** (`--cov-fail-under=70`, branch coverage on).

Integration tests are opt-in, because they need containers:

```bash
pytest -q --run-integration
```

Releases are tag-driven: pushing a `v*` tag runs the Release workflow (tests, build, publish).

## Development process

This project was built in an AI-native workflow. Implementation code was produced by AI coding
agents inside an agent harness I designed — requirements slots, instructions, constraints and
acceptance criteria that I defined up front.

My role:

- product requirements and the API surface of each module;
- task decomposition into independent engineering stages;
- context engineering: agent instructions, constraints, working rules;
- the specification → generation → run → verify → fix loop;
- result validation, testing and code review;
- control over CI, versioning and backwards compatibility of the public API.

Implementation code was generated with AI coding agents under human-led engineering control.

The full process, an `AGENTS.md` template and review checklists live in
[agentic-development-playbook](https://github.com/ninelegsdog/agentic-development-playbook).

## Compatibility note

`PaymentProvider` is a `Protocol`, not a base class: adapters can be added without touching
this package. The public surface of `payments.py` and `metrics.py` is what the bots depend on —
changes there require a version bump, because all nine bots pin a specific tag.

## License

MIT — see [LICENSE](LICENSE).