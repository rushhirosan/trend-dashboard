---
name: weekly-public-post-comments
description: >-
  REQUIRED every Monday after the mechanical weekly job: add same-week
  published-article comments to note and Substack. Never leave ranks+URL only.
  Use whenever docs/summaries/weekly/note or weekly/substack has a new
  YYYY-Www.md, the user mentions Wxx / note / Substack / 週次 / コメント / 深掘り,
  mechanical weekly summary just landed, or the post still has a bare URL /
  og:description under a topic. Do this pass every week without being asked.
---

# Weekly note / Substack comments

## Mandatory every week

**Do this pass every ISO week. Do not wait for the user to ask.**

Primary runner: the Cursor Automation **Weekly note/Substack comments**
(Monday ~07:00 JST, after the mechanical GHA lands ~06:30). Chat agents still
run the same checklist when the automation missed a week or the user opens a
draft that is still ranks+URL only.

When `docs/summaries/weekly/note/YYYY-Www.md` or `weekly/substack/YYYY-Www.md`
appears from the mechanical job (GHA commit message like
`docs(summaries): mechanical weekly summary`), treat the draft as incomplete
until each hot topic has a real comment paragraph. Ranks + bare URL, or an
og:description / plot blurb / author bio pasted under the ranks, is not done.

Checklist (Monday, after the weekly job, before paste to note/Substack):

1. Open the newest `note/YYYY-Www.md` and `substack/YYYY-Www.md`.
2. For every topic that is still ranks + URL (or a non-article gist), find a
   same-week published page, open it, and write one comment paragraph.
3. Replace the bare observation URL when the comment URL replaces it.
4. Stop only when all topics either have a proper comment or were already left
   alone because they already had one.

Do not change ranks, headings, the lead, or the footer.

Spec: `docs/summaries/weekly/brief_note_substack.md`. Pattern files: the previous
one or two `docs/summaries/weekly/note/YYYY-Www.md` and
`docs/summaries/weekly/substack/YYYY-Www.md` (e.g. W43 / W44 after comments).

## What generation already did (incomplete by design)

`scripts/generate_ai_weekly_summary.py` calls `fetch_public_page_gist` on the
observation URL only. That is not the finished post.

- Google search URLs are skipped. The line under the ranks is only the URL.
- Rakuten, YouTube, and store pages often return no lead, or a lead that is not
  an article.
- Wikipedia and news URLs sometimes get a lead. A generic intro ("The following
  notable deaths occurred…"), TMDB plot text, or a Qiita/author self-intro meta
  is not a comment. A specific lead (film, director, release) can stay only if
  it already reads like a concrete fact paragraph; otherwise rewrite from a
  proper same-week page.

Outputs the job writes (still need this skill afterward):

- `docs/summaries/weekly/note/YYYY-Www.md` (Japanese)
- `docs/summaries/weekly/substack/YYYY-Www.md` (English)

## Comment rules

Write only what that page states. Do not explain the rank from a different
story, and do not guess why it trended.

- Same ISO week as the post (Monday–Sunday JST). A publisher page for the same
  work may be older when the topic already used that page in a prior week
  (example: HUNTER×HUNTER 39 and the Shueisha contents page), or when the
  observation URL is itself the article (example: a Qiita post from earlier in
  the month). Prefer a same-week page when one exists.
- One short paragraph, then the article URL on the same line. Remove the bare
  observation URL when the comment URL replaces it.
- Japanese: `日付、媒体は、〜と書きました。〜とも書いています。 URL`
- English: `On DATE, OUTLET reported that …. URL` or one concrete fact from the
  page (who, what, when), not the boilerplate intro.
- Open the page and check the date and the sentences before writing. A title
  alone is not enough.
- Leave a topic alone when it already has a specific comment in the right form.

## Do not add

- The weekly brief list, category explainers, or an email / Gumroad pitch
- A reason that is not in the cited page
- A second comment that repeats the rank paragraph

## Do not skip

- Skipping because the mechanical gist "looks like enough"
- Shipping note/Substack paste while any topic is still URL-only
- Waiting for the user to say「また分析がない」
