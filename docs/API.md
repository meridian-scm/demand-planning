# API Reference

The full, always-current reference is the auto-generated OpenAPI docs served
by the running backend:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`
- Raw OpenAPI JSON: `http://localhost:8000/api/openapi.json`

This page is a hand-written summary of the resources for quick reference; it
does not attempt to duplicate every field — see the schemas in
[`backend/app/schemas/`](../backend/app/schemas) for that.

All endpoints are under the `/api/v1` prefix. Errors use one envelope:

```json
{ "error": { "code": "not_found", "message": "Product 9999 not found.", "details": {} } }
```

| HTTP status | `error.code` |
|---|---|
| 404 | `not_found` |
| 409 | `conflict` |
| 422 | `validation_error` / `insufficient_history` |
| 502 | `upstream_unavailable` |

## Products — `/products`

| Method | Path | Purpose |
|---|---|---|
| GET | `/products` | List/search/filter (paginated) |
| GET | `/products/{id}` | Get one |
| POST | `/products` | Create (409 on duplicate SKU) |
| PATCH | `/products/{id}` | Partial update |
| DELETE | `/products/{id}` | Deactivate (soft delete — history is preserved) |

## Locations — `/locations`

`GET /locations`, `POST /locations`.

## Sales history — `/sales`

| Method | Path | Purpose |
|---|---|---|
| GET | `/sales` | List, filterable by product/date range |
| POST | `/sales/bulk` | Upsert a JSON batch (used by manual-entry UI) |
| POST | `/sales/upload` | Upload a CSV (`multipart/form-data`, field `file`) — see [Data Upload page](../frontend/src/pages/DataUploadPage.tsx) for the accepted column formats |

## Inventory — `/inventory`

`GET /inventory?product_id=`, `POST /inventory` (upsert by product+location+date).

## Forecasts — `/forecasts`

| Method | Path | Purpose |
|---|---|---|
| POST | `/forecasts/runs` | Run a full forecasting cycle (all active products by default) + refresh exceptions |
| GET | `/forecasts/runs` | List past runs |
| GET | `/forecasts/runs/{id}` | Get one run |
| GET | `/forecasts/runs/{id}/lines` | Forecast line items for a run |
| GET | `/forecasts/preview/{product_id}` | Ad-hoc, **unsaved** forecast for what-if analysis |

`POST /forecasts/runs` body:
```json
{ "horizon": 6, "model": "auto", "product_ids": null, "detect_exceptions": true }
```
`model` is one of `auto`, `naive`, `moving_average`, `linear_trend`,
`holt_linear`, `holt_winters`, `seasonal_naive`.

## Exceptions — `/exceptions`

| Method | Path | Purpose |
|---|---|---|
| GET | `/exceptions` | List, filterable by `status`, `severity`, `exception_type`, `product_id` |
| PATCH | `/exceptions/{id}` | Update status: `open` → `acknowledged`/`resolved`/`dismissed` |
| POST | `/exceptions/products/{product_id}/refresh` | Re-run detection for one product on demand |

## Insights (AI) — `/insights`

| Method | Path | Purpose |
|---|---|---|
| POST | `/insights` | Generate a narrative. `scope`: `portfolio` or `product` (`product_id` required for the latter) |
| GET | `/insights` | List previously generated insights |

Every response includes `generated_by` (`"ollama"` or `"template"`) — the
frontend must not claim a template summary came from the LLM.

## Analytics — `/analytics`

| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/summary` | Dashboard KPI tiles |
| GET | `/analytics/timeline?product_id=` | Actuals + forecast on one timeline (portfolio-wide if `product_id` omitted) |
| GET | `/analytics/trends` | Products ranked by recent growth/decline |
| GET | `/analytics/categories` | Demand + forecast totals by category |
| GET | `/analytics/exceptions/breakdown` | Open exception counts by type/severity |
| GET | `/analytics/products/{id}` | Everything the product drill-down page needs, in one call |

## Health — `/api/health` (no `/v1` prefix)

Returns `status`, `version`, `environment`, `database` connectivity, and
which `ai_provider` is configured.
