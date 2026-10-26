---
name: weekly-public-post-comments
description: >-
  Adds same-week published-article comments to Trend Dashboard weekly note and
  Substack drafts after mechanical generation leaves only ranks and a URL.
  Use when editing docs/summaries/weekly/note or weekly/substack, or when the
  user says the weekly post is ranks only, missing 深掘り, コメント, note, or Substack.
---

# Weekly note / Substack comments

Mechanical generation writes ranks plus a URL. A usable post also has one comment paragraph per topic, taken from a published page. Do that pass every week. Do not change ranks, headings, the lead, or the footer.

Spec: `docs/summaries/weekly/brief_note_substack.md`. Pattern files: the previous one or two `docs/summaries/weekly/note/YYYY-Www.md` and `docs/summaries/weekly/substack/YYYY-Www.md`.

## What generation already did

`scripts/generate_ai_weekly_summary.py` calls `fetch_public_page_gist` on the observation URL.

- Google search URLs are skipped. The line under the ranks is only the URL.
- Rakuten, YouTube, and store pages often return no lead, or a lead that is not an article.
- Wikipedia and news URLs sometimes get a lead. A generic intro ("The following notable deaths occurred…") is not a comment. A specific lead (film, director, release) can stay.

Outputs:

- `docs/summaries/weekly/note/YYYY-Www.md` (Japanese)
- `docs/summaries/weekly/substack/YYYY-Www.md` (English)

## Comment rules

Write only what that page states. Do not explain the rank from a different story, and do not guess why it trended.

- Same ISO week as the post (Monday–Sunday JST). A publisher page for the same work may be older when the topic already used that page in a prior week (example: HUNTER×HUNTER 39 and the Shueisha contents page). Reuse that paragraph instead of finding a new one.
- One short paragraph, then the article URL on the same line. Remove the bare observation URL when the comment URL replaces it.
- Japanese: `日付、媒体は、〜と書きました。〜とも書いています。 URL`
- English: `On DATE, OUTLET reported that …. URL` or one concrete fact from the page (who, what, when), not the boilerplate intro.
- Open the page and check the date and the sentences before writing. A title alone is not enough.
- Leave a topic alone when it already has a specific comment.

## Do not add

- The weekly brief list, category explainers, or an email / Gumroad pitch
- A reason that is not in the cited page
- A second comment that repeats the rank paragraph
