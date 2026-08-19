# 3. AI narratives degrade to a deterministic fallback; frontend is Docker-first

## Status
Accepted

## Context
Two environment constraints shaped implementation decisions: (1) Ollama is an
optional local service, not guaranteed to be running, and the AI brief
explicitly frames it as "Local LLM"; (2) the build machine has Docker but not
Node.js installed, so a React frontend can be written but not run/tested on
the host directly.

## Decision
- `InsightService` always attempts the configured provider
  (`AI_PROVIDER=ollama|groq`) first when `AI_ENABLED=true`, and transparently
  falls back to a deterministic, dependency-free `TemplateProvider` on *any*
  failure — connection refused, timeout, missing API key, malformed JSON from
  the model. The planning workflow (forecasts, exceptions, the dashboard)
  never depends on the LLM being reachable.
- A second provider, `GroqProvider`, was added on request alongside Ollama —
  same `InsightProvider` protocol, same JSON-contract system prompt, same
  failure-tolerant parsing, different transport (Groq's hosted,
  OpenAI-compatible `/chat/completions` API instead of a local daemon). This
  is what the provider abstraction was designed for: swapping or adding an
  LLM backend is a new ~40-line class, not a change to `InsightService`, the
  routers, or the frontend.
- Every generated insight records `generated_by` (`"ollama"`, `"groq"`, or
  `"template"`) and `model_name`, and the frontend surfaces that provenance
  (`"<model> via <provider>"` or `"template summary"`) rather than implying
  every summary was model-written, or always by the same model.
- The frontend is built to run via Docker (`frontend/Dockerfile`,
  `docker-compose.yml`) as the primary supported path, rather than assuming
  local Node. The full test suite (unit, integration, E2E) is designed to run
  identically whether Node is installed locally or only available inside a
  container.

## Consequences
- The system is demoable and fully functional with zero AI infrastructure
  running — `AI_ENABLED=false` (or Ollama simply not started) still produces
  business-readable summaries, just via the template path. This is also what
  makes the backend test suite deterministic: tests run with `AI_ENABLED=false`
  so no test depends on network access or a running model.
- Users who *do* run Ollama get materially better prose with zero code
  changes — same context, same schema-constrained JSON contract, different
  provider.
- The frontend's own `npm test`/`npm run build` and the Playwright E2E suite
  could not be executed directly on this host during development; they were
  validated by building/running inside Docker instead
  (`docker compose build frontend`, then `docker compose up`). See
  [`docs/TESTING.md`](../TESTING.md) for the exact commands and this
  limitation's practical effect on how the E2E suite is invoked.

## Alternatives considered
- **Fail the request when Ollama is down**: rejected — makes the entire
  planning UI's insight panel a single point of failure tied to an optional
  local service, which contradicts the brief's own framing of AI as
  augmentation ("AI-generated recommendations that help... teams make better
  business decisions") rather than a hard dependency.
- **Mock Ollama out of the frontend build entirely and skip E2E**: rejected —
  the E2E suite is part of the deliverable and is written to run against the
  real stack; it is documented as Docker-runnable rather than silently
  dropped because the host lacked Node.
