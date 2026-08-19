# Meridian — AI-Powered Demand Planning for Supply Chain Operations

An intelligent demand-planning application that analyzes historical sales and
inventory data to forecast future demand, detect planning exceptions, and
generate AI-written, business-readable recommendations for supply chain
teams.

> This repository started from a Streamlit + CSV + Pandas concept brief (kept
> below in [Original Concept](#original-concept)). It was built out as a
> production-shaped, multi-user system: **PostgreSQL** for storage and
> **FastAPI + React/TypeScript** for the API and UI, per the actual build
> request. See [`docs/adr/0001-...`](docs/adr/0001-postgres-and-react-over-csv-and-streamlit.md)
> for the reasoning.

## What's in this repository

| Path | What |
|---|---|
| [`backend/`](backend) | FastAPI service: forecasting engine, exception detection, AI narratives, REST API, Postgres via SQLAlchemy/Alembic |
| [`frontend/`](frontend) | React + TypeScript (Vite) single-page app |
| [`e2e/`](e2e) | Playwright end-to-end tests against the full running stack |
| [`docs/`](docs) | Architecture, ERD, API reference, design notes, ADRs, testing guide |
| [`data/samples/`](data/samples) | Example CSVs for the sales-history upload flow |
| [`docker-compose.yml`](docker-compose.yml) | One-command local stack: Postgres, backend, frontend (+ optional Ollama) |

## Quick start

**Prerequisites:** Docker Desktop (or compatible). Node.js and Python are
only needed if you want to run things outside containers.

```bash
git clone <this-repo>
cd demand-planning
docker compose up -d db
```

Wait for Postgres to report healthy, then run migrations and seed demo data:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.seed.cli
```

Bring up the full stack:

```bash
docker compose up -d
```

- API: <http://localhost:8000/api/docs> (interactive Swagger UI)
- App: <http://localhost:5173>
- Health check: <http://localhost:8000/api/health>

**Optional — AI narratives.** Without any of this, AI insights still work —
they degrade to a deterministic, template-based summary (see
[`docs/adr/0003-...`](docs/adr/0003-ai-fallback-and-containerized-frontend.md)).
Two LLM providers are supported, pick one:

*Local (Ollama, no API key needed):*
```bash
docker compose --profile ai up -d ollama
docker exec meridian-ollama ollama pull llama3.1
```

*Hosted (Groq — faster, no local model download):* create `backend/.env`
from `backend/.env.example`, set `AI_PROVIDER=groq` and `GROQ_API_KEY=<your
key from https://console.groq.com/keys>`, then restart the backend:
```bash
cp backend/.env.example backend/.env   # edit AI_PROVIDER and GROQ_API_KEY in this file
docker compose up -d --force-recreate backend
```
`GROQ_API_KEY` can also be set as a host environment variable instead of
`.env` — `docker-compose.yml` passes it through either way. Never commit a
real key; `.env` is gitignored.

### Running without Docker

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.seed.cli
uvicorn app.main:app --reload

# Frontend (separate terminal, requires Node 20+)
cd frontend
npm install
npm run dev
```

## Testing

```bash
# Backend: 134 tests (unit + integration), JUnit XML + coverage
cd backend && pytest tests -q

# Frontend: unit/component tests, JUnit XML + coverage
cd frontend && npm test

# End-to-end: Playwright against the full running stack
cd e2e && npm install && npx playwright install --with-deps chromium && npm test
```

Full details, markers, and what each layer covers: [`docs/TESTING.md`](docs/TESTING.md).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, forecasting engine, exception rules, AI layer
- [`docs/ERD.md`](docs/ERD.md) — database schema
- [`docs/API.md`](docs/API.md) — REST API reference (or `/api/docs` on a running instance)
- [`docs/DESIGN.md`](docs/DESIGN.md) — UI design notes
- [`docs/TESTING.md`](docs/TESTING.md) — how to run every test layer
- [`docs/adr/`](docs/adr) — architecture decision records

## Core capabilities

- **Demand forecasting** — 6 algorithms (naive, moving average, linear
  trend, Holt linear, seasonal naive, Holt-Winters) with automatic
  backtested model selection and prediction intervals.
- **Trend analysis** — growing/declining products ranked by recent vs.
  prior-period demand, by category and portfolio-wide.
- **Exception detection** — demand spikes/drops, stockout risk, excess
  inventory, low-confidence forecasts, and volatile new products, each with
  the metric that triggered it and a specific recommendation.
- **AI insights** — a pluggable LLM layer (local Llama 3.1 via Ollama, or
  hosted models via Groq) generates business-readable summaries and
  recommendations at the portfolio or product level, with an honest,
  always-available deterministic fallback when no provider is configured.
- **CSV ingestion** — flexible column-name matching, row-level validation
  and error reporting, safe re-upload (upsert, not duplicate).

## Worked example (from the original brief)

Given monthly demand of 100, 120, 140, 160 units, the linear-trend model
(auto-selected by backtest) forecasts **180 units** for the next period —
reproduced exactly in
[`backend/tests/unit/test_forecast_engine.py`](backend/tests/unit/test_forecast_engine.py).

---

## Original Concept

<details>
<summary>The initial project brief this system was built from (click to expand)</summary>

### Overview

AI-Powered Demand Planning for Supply Chain Operations is an intelligent
solution designed to help supply chain teams improve demand forecasting and
planning through data-driven insights and Artificial Intelligence. The
application analyzes historical sales and inventory data to predict future
demand, identify demand trends, detect planning exceptions, and provide
recommendations that help planners make better inventory and replenishment
decisions.

### Business Challenge

Demand planning is a critical supply chain activity that directly impacts
inventory levels, customer satisfaction, and operational efficiency. Many
organizations rely on manual analysis and spreadsheets to review historical
sales data, forecast future demand, identify changing demand patterns,
monitor inventory availability, detect planning risks, and make
replenishment decisions — activities that are often time-consuming,
reactive, and prone to human error.

### Target Users

Demand Planners · Supply Chain Analysts · Inventory Managers · Supply Chain
Managers · Operations Teams

### Example Use Cases

**Forecast Next Month Demand** — Input: Jan 100, Feb 120, Mar 140, Apr 160
units sold → AI Forecast: 180 units for May → Recommendation: increase
replenishment quantities to support rising demand.

**Demand Spike Detection** — Product A demand increased 25% vs. the
previous month → Recommendation: review inventory levels and ensure
replenishment plans are aligned with forecasted demand.

**Inventory Risk Alert** — Current inventory levels may not support
projected demand over the next planning period → Recommendation: review
inventory strategy and replenishment schedule.

### Original Technology Stack (as briefed)

Frontend: Streamlit · Data Processing: Python + Pandas · Data Storage: CSV
Files · AI: Ollama (Local LLM) + Llama 3.1 · Visualization: Streamlit
Charts + Plotly

*(Superseded in this implementation by PostgreSQL + FastAPI + React, per the
actual build request — see the [Architecture doc](docs/ARCHITECTURE.md) and
[ADR 0001](docs/adr/0001-postgres-and-react-over-csv-and-streamlit.md). The
AI layer, Ollama + Llama 3.1, was kept as specified.)*

### Elevator Pitch

AI-Powered Demand Planning for Supply Chain Operations helps demand
planners forecast future demand, identify planning exceptions, analyze
demand trends, and generate actionable recommendations, enabling more
accurate planning and smarter inventory decisions.

</details>
