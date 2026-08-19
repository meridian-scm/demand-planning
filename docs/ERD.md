# Entity-Relationship Diagram

```mermaid
erDiagram
    PRODUCT ||--o{ SALES_HISTORY : "has"
    PRODUCT ||--o{ INVENTORY_SNAPSHOT : "has"
    PRODUCT ||--o{ FORECAST : "has"
    PRODUCT ||--o{ PLANNING_EXCEPTION : "has"
    PRODUCT ||--o{ INSIGHT : "has"
    LOCATION ||--o{ SALES_HISTORY : "at"
    LOCATION ||--o{ INVENTORY_SNAPSHOT : "at"
    FORECAST_RUN ||--o{ FORECAST : "produces"

    PRODUCT {
        int id PK
        string sku UK
        string name
        string category
        string subcategory
        numeric unit_cost
        numeric unit_price
        int lead_time_days
        int safety_stock_units
        int reorder_point_units
        bool active
    }

    LOCATION {
        int id PK
        string code UK
        string name
        string region
        string country
        bool active
    }

    SALES_HISTORY {
        int id PK
        int product_id FK
        int location_id FK
        date period_start
        int units_sold
        numeric revenue
        string channel
        string source
    }

    INVENTORY_SNAPSHOT {
        int id PK
        int product_id FK
        int location_id FK
        date snapshot_date
        int on_hand_units
        int on_order_units
        int allocated_units
    }

    FORECAST_RUN {
        int id PK
        string run_label
        string requested_model
        int horizon_periods
        int products_forecasted
        int products_skipped
        datetime started_at
        datetime completed_at
        json notes
    }

    FORECAST {
        int id PK
        int run_id FK
        int product_id FK
        date period_start
        float forecast_units
        float lower_bound_units
        float upper_bound_units
        string model_used
        float mape
        float wape
        float rmse
        float confidence_level
        json model_params
    }

    PLANNING_EXCEPTION {
        int id PK
        int product_id FK
        string exception_type
        string severity
        string status
        date detected_for_period
        string title
        string message
        string recommendation
        float metric_value
        float baseline_value
        float deviation_pct
        json context
    }

    INSIGHT {
        int id PK
        string scope
        int product_id FK
        string headline
        string summary
        json recommendations
        string generated_by
        string model_name
        json context
    }
```

## Notable constraints

- `sales_history`: unique on `(product_id, location_id, period_start)`,
  indexed on `(product_id, period_start)` for the timeline queries.
- `inventory_snapshots`: unique on `(product_id, location_id, snapshot_date)`.
- `forecasts`: unique on `(run_id, product_id, period_start)`.
- `planning_exceptions`: indexed on `(status, severity)` for the alerts
  queue, and `(product_id, exception_type)` for the product drill-down.
- All product-owned tables cascade-delete when the parent `Product` is
  deleted (the API only exposes soft-delete/deactivation, but the schema
  supports a real delete for data cleanup/testing).

Generated from the SQLAlchemy models in
[`backend/app/models/`](../backend/app/models); the live schema is created by
the Alembic migration in
[`backend/alembic/versions/`](../backend/alembic/versions).
