# Trend Dashboard — agent context

- **Product rules**: `.cursor/rules/trend-dashboard.mdc` (always-on conventions).
- **Repo map / Flask / Fly**: `.cursor/skills/trend-dashboard-repo/SKILL.md`.
- **Templates / Bootstrap / static JS**: `.cursor/skills/trend-dashboard-ui/SKILL.md`.
- **Trend sources, scheduler, caching**: `.cursor/skills/trend-sources-pipeline/SKILL.md`.
- **Paid summary experiment (Pattern A, phase 1)** — delivery timeboxes, Markdown templates, checklists: `docs/summary_pattern_a_phase1.md`.
- **Summary drafts (repo only, not served by the site)** — `docs/summaries/` (see `docs/summaries/README.md`).

When editing UI for the AI summary preview card: `templates/partials/ai_summary_fake_door.html` (Top1 + “coming soon” modal), `static/js/ai-summary-fake-door.js` (GA: `ai_summary_top5_click`, `fake_door_view`).
