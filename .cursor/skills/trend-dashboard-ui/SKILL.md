---
name: trend-dashboard-ui
description: Guides Trend Dashboard HTML templates, Bootstrap 5.1.3, static JS/CSS, and JP/US page patterns for a minimal one-screen feel. Use when editing templates, static assets, layout, regional views, or when the user mentions UI, Bootstrap, or frontend behavior.
---

# Trend Dashboard — UI and Static Assets

Stack: **HTML templates**, **Bootstrap 5.1.3**, **Font Awesome**, vanilla **JavaScript** (no large SPA framework).

## Layout

| Area | Path |
|------|------|
| Templates | `templates/` (e.g. `index.html`, `us_trends.html`, `about.html`, `data-status.html`) |
| Styles | `static/css/` (`main.css`, feature-specific CSS) |
| Scripts | `static/js/` (`app.js`, `app-common.js`, region- or feature-specific JS) |

## Principles (align with project rules)

- **One-screen** comprehension where possible; clear **section hierarchy** and scanability.
- Prefer **Bootstrap** components and utilities before custom design systems.
- Avoid competing visual noise; **practical** tweaks over flashy redesigns.
- **Desktop** scanning matters; **mobile** should stay readable—responsive tweaks, not a separate product.

## Regional / multi-page patterns

Japan-focused and US-focused views may use different templates and JS entry points (e.g. `us-trends.js`, `us_trends.html`). When adding UI, mirror existing naming and structure so behavior stays predictable.

## When changing UI

1. Identify the template and any **page-specific** JS/CSS already used there.
2. Reuse patterns from `main.css` / `app-common.js` before adding new globals.
3. Keep new interactions cheap—fewer steps to see the current state.
4. If backend contracts change (JSON shape, URLs), update routes and any **tests** that assert on pages or APIs.

## Assets

Place icons and images under `static/` following existing folders. Do not introduce a new front-end framework unless there is a strong, explicit reason.
