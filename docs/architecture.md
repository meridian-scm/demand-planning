# Architecture boundaries

Meridian is a modular monolith. Dependency direction is inward:

```text
API and infrastructure → application services → domain
```

- `domain` contains framework- and storage-independent planning concepts.
- `application` coordinates use cases through repository ports.
- `ports` define contracts required by application services.
- `infrastructure` will implement those ports for DuckDB and Parquet in a later step.
- `api` translates HTTP requests and responses without owning business rules.

The frontend communicates only with the FastAPI boundary. It never accesses analytical artifacts
directly. The current Step 1 foundation contains no forecasting, DuckDB, or Parquet implementation.
