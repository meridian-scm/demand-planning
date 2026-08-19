# UI Design Notes

## Visual language

Dark-first, data-dense, single accent-pair palette (`--color-primary`
blue-violet for forecasts/primary actions, `--color-accent` teal for actuals)
so the two most important chart series (actual vs. forecast) are
distinguishable at a glance without a legend. Severity/status colors are
consistent everywhere they appear (badge on the exceptions table, KPI delta
on the dashboard, filter chips): green = healthy/resolved, amber = medium/
acknowledged, red = high, pink-red = critical.

Design tokens live in [`frontend/src/styles/theme.css`](../frontend/src/styles/theme.css)
as CSS custom properties — every color, radius, and shadow used by the app
references one of these, so a rebrand or a light-theme variant is a
single-file change.

## Layout

Fixed left sidebar (232px) + fluid main content, collapsing to a single
column with the sidebar hidden below 980px (the app is planner-desk software
first; mobile is "doesn't break," not a primary target). Every page follows
the same shell: a page header (title + one-line subtitle + primary action),
then a KPI row where relevant, then one or two content cards.

## Screens

| Route | Purpose |
|---|---|
| `/` | Dashboard — portfolio KPIs, demand chart, AI portfolio insight, category breakdown, trending products |
| `/products` | Searchable product list + inline creation form |
| `/products/:id` | Product drill-down — KPIs, demand chart, AI product insight, this product's open exceptions |
| `/exceptions` | Exception queue with status/severity filter chips and inline Ack/Resolve actions |
| `/forecast` | Forecast-cycle trigger (horizon, model) + run history |
| `/data` | CSV upload with an inline format reference and a row-level import report |

## Key interaction decisions

- **AI insight provenance is never hidden.** The insight panel always shows
  whether the text came from Llama 3.1 or the deterministic template
  fallback (`InsightPanel.tsx`) — matching the backend's `generated_by`
  field. This was a deliberate call: a business tool that silently claims
  every summary is AI-written when the model might be unreachable would
  mislead planners about how much to trust the wording (the *numbers* are
  identical either way — only the prose differs).
- **Exceptions default to the `open` filter.** The queue a planner actually
  works from is the default view; resolved/dismissed history is one click
  away, not the default noise.
- **CSV upload always shows a row-level report**, including rejected rows
  and unknown SKUs, rather than a bare success/failure toast — matching how
  the backend's `IngestionReport` is designed (see `docs/API.md`).
- **Forecast preview vs. forecast run** are distinct actions:
  `/forecasts/preview/{id}` (used nowhere in the current UI but exposed on
  the API for a future what-if panel) never writes to the database;
  `/forecasts/runs` always does. The distinction is enforced in the backend,
  not just the UI, so a scripted client can't blur it either.

## What was deliberately left out of v1

- Bulk product edit / CSV product-master upload (only sales history is
  bulk-uploadable — product master data is a smaller, lower-churn dataset
  for the target users).
- Manual forecast override / consensus planning workflow (the exception
  "forecast_anomaly" rule flags when a planner *should* override, but
  capturing the override itself is a natural v2).
- Auth/RBAC — out of scope for this build; see
  [`docs/adr/0001-postgres-and-react-over-csv-and-streamlit.md`](adr/0001-postgres-and-react-over-csv-and-streamlit.md)
  for the architectural seam (a stable REST API) that makes adding it later
  straightforward (a dependency on every router, not a rewrite).
