# 1. PostgreSQL + FastAPI + React instead of CSV + Streamlit

## Status
Accepted

## Context
The project brief specified CSV files for storage, Streamlit for the UI, and
Python/Pandas for processing — a single-analyst, single-process notebook-style
tool. The actual request was to build with PostgreSQL as the backend and to
choose "a better technology" for the UI given that stack.

## Decision
- **PostgreSQL** replaces CSV files as the system of record for products,
  locations, sales history, inventory snapshots, forecasts, and exceptions.
- **FastAPI** replaces the implicit "Streamlit script does everything"
  architecture with a REST API and a persistence-agnostic service layer.
- **React + TypeScript (Vite)** replaces Streamlit as the UI, talking to the
  API over HTTP.

## Consequences
- Multi-user access (several planners working concurrently) is now safe;
  CSV files have no locking or transaction semantics.
- The API has a stable, versioned, testable contract independent of the UI
  — anything (a scheduler, a script, a different frontend) can drive a
  forecast run or read the dashboard without going through the browser.
- Forecasts are versioned (`forecast_runs` + `forecasts`, one row per period
  per product per run) rather than a single mutable "current forecast" —
  which CSV-file storage would have made awkward to do safely.
- Cost: more moving parts to run locally (Postgres, two dev servers) than a
  single `streamlit run app.py`. Mitigated with `docker-compose.yml` — the
  whole stack comes up with one command.
- The team must know SQL/Alembic migrations instead of just Pandas. Given the
  target users (a supply-chain analytics team, not exclusively data
  scientists), this is judged an acceptable tradeoff for the durability and
  concurrency it buys.

## Alternatives considered
- **Dash (Plotly)** instead of React: stays 100% Python, no Node dependency
  anywhere. Rejected in favor of React because the user explicitly asked for
  "a better technology" for the UI, and React/TypeScript is materially more
  capable for a production multi-page app (routing, component reuse, a much
  larger ecosystem, TypeScript's compile-time safety) — the tradeoff being
  that Node is required to build/run it, which this host doesn't have
  installed. That is mitigated by fully containerizing the frontend (see
  ADR 0003).
- **Django** instead of FastAPI: heavier, brings its own ORM/admin/templating
  that isn't needed for a pure API. FastAPI's native Pydantic integration and
  automatic OpenAPI docs were a better fit for a React-consumed API.
