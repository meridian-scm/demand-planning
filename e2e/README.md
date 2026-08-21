# End-to-end tests

The Playwright suite lives in `frontend/e2e` so it uses the frontend's pinned Node dependencies. It
starts FastAPI and Vite, waits for backend readiness and the browser application, then exercises the
primary Demand Planner journey against the deterministic `test-v1` artifacts.

Before running it locally, generate the small data and forecast-run artifacts using the verified
commands in the root README. Then run:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

The suite covers operational readiness, Overview, Store + SKU selection, historical demand,
statistical forecast generation and intervals, validation metrics, signals, inventory risk, planning
exceptions, and immutable Forecast Runs. CI retains the Playwright trace, screenshot, video, and HTML
report when a browser journey fails.
