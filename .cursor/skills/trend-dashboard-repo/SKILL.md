---
name: trend-dashboard-repo
description: Maps the Trend Dashboard repository layout, Flask entry points, blueprints, config, and deployment touchpoints. Use when navigating the codebase, adding routes or app wiring, or when the user mentions app.py, wsgi, Fly.io, or project structure.
---

# Trend Dashboard — Repository Map

Product philosophy and conventions live in `.cursor/rules/trend-dashboard.mdc`. This skill is **where things are** and **how the app boots**.

## Entry points

| Path | Role |
|------|------|
| `app.py` | `create_app()`, registers blueprints, scheduler wiring for local `main()` |
| `wsgi.py` | Gunicorn / production: imports `create_app()`, starts scheduler with worker-safe behavior |

## HTTP layer

| Path | Role |
|------|------|
| `routes/trend_routes.py` | Trend-related blueprint (`trend_bp`) |
| `routes/data_routes.py` | Data / status blueprint (`data_bp`) |
| `services/subscription/subscription_routes.py` | Subscription blueprint |

## Configuration and env

| Path | Role |
|------|------|
| `config/app_config.py` | Central config; `USE_DUMMY_DATA` is synced to `os.environ` in `create_app()` |
| `.env` | Local secrets (not committed); see `.env.example` |

## Shared infrastructure

| Path | Role |
|------|------|
| `database_config.py` | `TrendsCache` and DB access patterns used by managers |
| `utils/logger_config.py` | Logging |
| `utils/rate_limiter.py` | Per-service rate limiting |
| `utils/dummy_data_generator.py` | Dummy trend data when dummy mode is on |

## Tests

| Path | Role |
|------|------|
| `tests/` | Pytest; extend when changing routes, UI contracts, or scheduler email |

## Deployment and ops

| Path | Role |
|------|------|
| `fly.toml` | Fly.io app config |
| `scripts/release.sh` | Preflight: `pytest`, secret scan; optional `--ship` / `--deploy` |

## When adding a feature

1. Decide whether it belongs in **routes**, **services**, **managers**, or **templates/static** (see `trend-sources-pipeline` and `trend-dashboard-ui` skills).
2. Register new blueprints in `create_app()` only when a new blueprint is required; prefer extending existing blueprints when it keeps boundaries clear.
3. Keep fetching, normalization, and rendering separated—match existing patterns in the touched area.
