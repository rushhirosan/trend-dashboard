---
name: trend-sources-pipeline
description: Guides Trend Dashboard data collection, BaseTrendsManager subclasses, manager registration, PostgreSQL cache, APScheduler jobs, and external API handling. Use when adding or changing trend sources, managers, scheduler, caching, rate limits, or USE_DUMMY_DATA behavior.
---

# Trend Dashboard — Sources and Scheduler

Prefer **official APIs** over scraping. Treat sources as **unreliable**: timeouts, empty payloads, and malformed responses are normal.

## Core pieces

| Path | Role |
|------|------|
| `services/trends/base_trends_manager.py` | `BaseTrendsManager`: cache, rate limiter, dummy mode, shared fetch/error behavior |
| `services/trends/*_trends.py` | One module per source; implements concrete manager (e.g. `GoogleTrendsManager`) |
| `managers/trend_managers.py` | Builds manager instances, `MANAGER_CONFIGS` list, parallel refresh orchestration |
| `services/scheduler/scheduler_manager.py` | APScheduler: when full refreshes run, locking across workers |

## Adding or changing a source

1. Implement (or extend) a manager class—typically subclass `BaseTrendsManager` in `services/trends/<name>_trends.py`.
2. Register the manager in `managers/trend_managers.py` (`MANAGER_CONFIGS` and imports). Keep the internal key stable if routes or JS depend on it.
3. Wire any new API routes or template/JS only if the product needs a new surface; reuse existing JSON/HTML patterns when possible.
4. Respect **rate limits** and **cache keys**; align refresh frequency with how often the source actually updates.
5. With **`USE_DUMMY_DATA`**, APIs should not be required for local UI work—dummy paths go through `utils/dummy_data_generator` where applicable.

## Persistence

`TrendsCache` (`database_config.py`) backs **current display / cache efficiency**, not a general history product. Do not add historical time-series storage unless the product explicitly requires it and scope is documented.

## Scheduler

Scheduled jobs are defined in `services/scheduler/scheduler_manager.py`. Changes should remain **observable** (logs on success/failure). Avoid silent failures in background refresh.

## Checklist for a new integration

- [ ] Prefer API over scrape; document source-specific caveats in code comments if non-obvious.
- [ ] Handle empty and partial results without breaking the whole dashboard.
- [ ] Register in `trend_managers.py` if the source participates in global refresh.
- [ ] Run tests touching managers/routes if behavior is critical (`tests/`).
