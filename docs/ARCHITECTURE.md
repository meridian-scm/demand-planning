# Architecture

## System overview

```
┌─────────────────────┐        HTTPS/JSON         ┌──────────────────────────┐
│   React + TypeScript │  ────────────────────────▶ │      FastAPI backend     │
│   (Vite, React Query)│  ◀──────────────────────── │   (Python 3.11, Uvicorn) │
└─────────────────────┘                             └───────────┬──────────────┘
                                                                  │ SQLAlchemy 2.0
                                                                  ▼
                                                      ┌──────────────────────────┐
                                                      │       PostgreSQL 16       │
                                                      └──────────────────────────┘

                                                      ┌──────────────────────────┐
                                          optional    │   Ollama (Llama 3.1)      │
                                          local LLM ─▶│   AI narrative generation │
                                                      └──────────────────────────┘
```

The backend is a single FastAPI service. There is no message queue, cache, or
background worker — forecast runs and exception detection execute
synchronously inside the request that triggers them, which is appropriate at
the data volumes a demand-planning team actually works with (thousands of
SKUs, monthly granularity). If that stops being true, the natural evolution is
to move `PlanningService.run_forecast` behind a task queue (Celery/RQ) without
changing its public contract.

## Why this stack (vs. the original brief)

The project brief specified Streamlit + CSV files + Ollama. That is a fine
shape for a single-analyst notebook-style tool. This build targets a
multi-user planning application instead, which changes two decisions:

- **PostgreSQL instead of CSV files.** Sales history, forecasts, and
  exceptions are relational, get queried with filters and joins (by category,
  by severity, by date range), and need concurrent writers (multiple planners
  uploading data, forecast runs, exception status updates). CSV files don't
  support any of that safely.
- **FastAPI + React instead of Streamlit.** Streamlit is excellent for a
  single Python process rendering its own UI to one user at a time. It has no
  real concept of a stable, versioned API, makes concurrent multi-user access
  awkward, and couples the UI framework to the Python runtime. A REST API
  (FastAPI, with OpenAPI docs for free) plus an independent SPA (React)
  separates those concerns, lets the frontend be deployed/scaled/cached
  independently, and gives every piece of functionality a stable HTTP
  contract that can be tested, scripted, or consumed by something other than
  the browser (e.g. a scheduled batch job that triggers a forecast run).

Ollama + Llama 3.1 is kept as specified — see [AI Layer](#ai-narrative-layer)
below for how the system degrades gracefully when it isn't running.

## Backend layout

```
backend/app/
├── main.py              FastAPI app factory, CORS, error handlers, /api/health
├── core/                 settings (pydantic-settings), logging, domain exceptions
├── db/                   SQLAlchemy engine/session, declarative base
├── models/                ORM models (Product, Location, SalesHistory,
│                          InventorySnapshot, ForecastRun, Forecast,
│                          PlanningException, Insight)
├── schemas/               Pydantic request/response models (1:1 with the API)
├── services/
│   ├── forecasting/        pure forecasting engine — no DB, no HTTP (see below)
│   ├── exceptions.py       pure exception-detection rules
│   ├── ai.py                AI narrative layer (Ollama + deterministic fallback)
│   ├── ingestion.py         CSV parsing/validation for sales history
│   ├── planning.py          orchestration: wires the pure engines to the DB
│   └── analytics.py         read-only aggregations for the dashboard
├── api/v1/routers/        one router per resource, thin — no business logic
└── seed/                   deterministic demo/test data generator
```

The forecasting and exception-detection code is deliberately isolated from
SQLAlchemy and FastAPI. `ForecastEngine.forecast()` takes a list of
`Observation` value objects and returns a `ForecastResult` — nothing else. The
same is true of `ExceptionDetector.detect()`. This is what makes 76 of the
project's unit tests run in under 2 seconds with no database at all, and it's
also what would let either module be lifted into a different service (a batch
job, a Lambda) without modification.

`PlanningService` in `services/planning.py` is the only place that knows
about both the pure engines and the database — it loads history, calls the
engine, and persists the result. Routers call `PlanningService` /
`AnalyticsService`; they never touch SQLAlchemy directly.

## Forecasting engine

Six algorithms are implemented on top of `numpy`, from first principles (no
`statsmodels`/`prophet` dependency, so the service has one fewer heavyweight
package to install and pin):

| Model | Use case |
|---|---|
| `naive` | Baseline every other model must beat |
| `moving_average` | Flat, low-volume SKUs |
| `linear_trend` | Steady growth/decline, short history (the README's worked example) |
| `holt_linear` | Trending demand, no seasonality, ≥3 periods |
| `seasonal_naive` | Strongly seasonal, ≥1 full season of history |
| `holt_winters` | Trend + seasonality, ≥2 full seasons of history |

**Model selection (`model=auto`, the default):** the engine holds out the
last `FORECAST_BACKTEST_HOLDOUT` periods (default 3), fits every model that
has enough history for the series length, scores each against the held-out
actuals using **WAPE** (weighted absolute percentage error — chosen over MAPE
because MAPE is undefined/explodes on the zero-demand periods that are normal
for slow-moving SKUs), and refits the winner on the full history to project
forward.

**Prediction intervals** are derived from the standard deviation of the
winning model's in-sample residuals, widened by `√horizon` per step (the
standard random-walk assumption for multi-step-ahead uncertainty), and scaled
by the z-score for the requested confidence level.

**Missing periods** in a product's history are filled with zero demand
(not skipped) before fitting — a month with no sales is information, and
silently compressing the series would corrupt every seasonal calculation.

See [`backend/app/services/forecasting/engine.py`](../backend/app/services/forecasting/engine.py)
and [`algorithms.py`](../backend/app/services/forecasting/algorithms.py).

## Exception detection

Six rules run over each product's history, forecast, and inventory position:

- **Demand spike / drop** — latest period deviates from a trailing baseline
  by both a percentage threshold *and* a z-score threshold, so naturally noisy
  low-volume SKUs don't flood the queue.
- **Stockout risk / excess inventory** — available stock (on-hand + on-order
  − allocated − safety stock) compared against forecast demand, expressed as
  periods of cover.
- **Forecast anomaly** — the winning model's backtest WAPE exceeds a
  reliability threshold; tells the planner "don't trust this number
  unadjusted."
- **New-product volatility** — short history with a high coefficient of
  variation; flags SKUs that shouldn't be planned on the statistical forecast
  alone yet.

Every exception carries the raw metric, baseline, and deviation that
triggered it (`context` JSON column) so a planner can see *why*, not just
*that*. See
[`backend/app/services/exceptions.py`](../backend/app/services/exceptions.py).

Exceptions are **regenerated per forecast run** for the `open` status only —
anything a planner has acknowledged, resolved, or dismissed survives the next
run untouched. That's implemented in
`PlanningService._refresh_exceptions`.

## AI narrative layer

Three providers implement the same `InsightProvider` protocol:

- **`OllamaProvider`** — calls a local Llama 3.1 through Ollama's
  `/api/generate`, with a system prompt that forces strict JSON output
  (`{"headline", "summary", "recommendations"}`) and a low temperature.
- **`GroqProvider`** — calls a hosted model (default
  `openai/gpt-oss-120b`) through Groq's OpenAI-compatible
  `/chat/completions` endpoint, using `response_format: {"type":
  "json_object"}` for the same strict-JSON contract. No local daemon —
  just `GROQ_API_KEY`. Selected with `AI_PROVIDER=groq`.
- **`TemplateProvider`** — a deterministic, rule-based narrator with no
  external dependency, used whenever the configured provider is disabled,
  unreachable, or misconfigured (e.g. `AI_PROVIDER=groq` with no API key set).

Both LLM providers share one JSON-extraction routine
(`_parse_narrative_json`) that tolerates the usual prose-wrapped response
("Sure, here you go: {...}") rather than trusting the model to return
nothing but JSON, since that's the single most common way this class of
integration breaks in practice.

`InsightService.generate()` always tries the configured provider first
(`AI_PROVIDER`, default `ollama`, when `AI_ENABLED=true`) and falls back to
the template provider on **any** failure — connection refused, timeout,
missing API key, malformed JSON, a non-2xx response. The planning workflow
never blocks on the LLM being available. Every generated `Insight` records
`generated_by` (`"ollama"`, `"groq"`, or `"template"`) plus `model_name`, and
the frontend surfaces that honestly (`"<model> via <provider>"`, or
`"template summary"`) rather than implying every summary came from a model,
let alone always the same one.

## Database schema

See the ER diagram in [`docs/ERD.md`](ERD.md) and the Alembic migration in
[`backend/alembic/versions/`](../backend/alembic/versions). Highlights:

- `sales_history` is unique on `(product_id, location_id, period_start)` —
  re-uploading a corrected CSV export updates in place rather than
  duplicating. Note: Postgres treats `NULL = NULL` as not-equal for unique
  constraints, so when `location_id` is NULL the *application* (not the DB)
  is responsible for the upsert-by-lookup behaviour — see
  `SalesIngestionService` and the regression test in
  `tests/integration/test_postgres_specific.py`.
- `forecasts` belong to a `forecast_runs` row rather than overwriting a
  single "current forecast" per product — every cycle is versioned and
  auditable.
- Deleting a `Product` cascades to its history, forecasts, and exceptions
  (`ondelete="CASCADE"`); the API exposes deactivation (`active=false`)
  rather than hard delete for that reason.

## Frontend layout

```
frontend/src/
├── api/          axios client + one function module per REST resource
├── types/api.ts   TypeScript types mirroring the backend Pydantic schemas
├── hooks/         React Query hooks (queries + mutations, cache invalidation)
├── components/    layout (sidebar/shell), charts (Recharts), reusable UI
├── pages/          one component per route
└── styles/         hand-written CSS (design tokens + component classes)
```

State management is React Query only — there is no Redux/Zustand global
store, because almost all UI state here *is* server state (products,
forecasts, exceptions) and React Query's cache + invalidation covers that
without extra machinery. Local component state (`useState`) handles the
handful of things that are genuinely UI-only (form inputs, active filter chip).

## Data flow: a planning cycle

1. Planner uploads a CSV (`POST /sales/upload`) → `SalesIngestionService`
   validates and upserts rows.
2. Planner (or a scheduler) triggers `POST /forecasts/runs` →
   `PlanningService.run_forecast` loads each active product's history, runs
   `ForecastEngine`, persists a `ForecastRun` + `Forecast` rows, and runs
   `ExceptionDetector` against the fresh forecast + latest inventory snapshot.
3. Dashboard (`GET /analytics/summary`, `/timeline`, `/trends`) reads the
   latest run's data for KPIs and charts.
4. Planner works the exception queue (`GET/PATCH /exceptions`), optionally
   asking for an AI narrative (`POST /insights`) on any product or the whole
   portfolio.
