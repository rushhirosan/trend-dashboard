#!/usr/bin/env python3
"""
Fill ``docs/x_post_samples/daily_series_from_2026-05-09.md`` for a given date
from the public Trend Dashboard JSON APIs (no direct calls to Google etc.).

Typical use: JST 20:00 after the 19:00 refresh job has populated cache.

  python scripts/generate_daily_x_post_series.py --write
  python scripts/generate_daily_x_post_series.py --date 2026-05-10 --dry-run

Env:
  TREND_DASHBOARD_BASE_URL  Base URL (default: https://trends-dashboard.fly.dev)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

BASE_DEFAULT = "https://trends-dashboard.fly.dev"
SERIES_REL = "docs/x_post_samples/daily_series_from_2026-05-09.md"
ANCHOR_HEADING = "## この先の日付を足すとき"


def fetch(base: str, path: str) -> dict:
    url = base.rstrip("/") + path
    r = requests.get(
        url,
        headers={"User-Agent": "trend-dashboard-daily-docs/1.0"},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()


def _rows(payload: dict) -> list:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return data
    return []


def first_field(row: dict, keys: tuple[str, ...], default: str = "") -> str:
    if not isinstance(row, dict):
        return default
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def clip(s: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= max_len:
        return s
    if max_len <= 1:
        return "…"
    return s[: max_len - 1] + "…"


def second_keyword(rows: list) -> str:
    if len(rows) < 2:
        return ""
    return first_field(rows[1], ("keyword", "title"))


def build_jp_block(base: str, d: str) -> str:
    gjp = fetch(base, "/api/google-trends?country=JP&force_refresh=false")
    yjp = fetch(base, "/api/youtube-trends?region=JP&force_refresh=false")
    nh = fetch(base, "/api/nhk-trends?force_refresh=false")
    wn = fetch(base, "/api/worldnews-trends?country=jp&force_refresh=false")
    z = fetch(base, "/api/zenn-trends?force_refresh=false")
    jpc = fetch(base, "/api/jpcert-trends?force_refresh=false")
    mj = fetch(base, "/api/music-trends?service=spotify&region=JP&force_refresh=false")
    mov = fetch(base, "/api/movie-trends?country=JP&force_refresh=false")

    r_g = _rows(gjp)
    k1 = first_field(r_g[0] if r_g else {}, ("keyword",), "…")
    k2 = second_keyword(r_g)
    g_line = f"{k1}／{k2}" if k2 else k1

    r_y = _rows(yjp)
    yt = first_field(r_y[0] if r_y else {}, ("title",), "…")

    r_n = _rows(nh)
    r_w = _rows(wn)
    nh_t = first_field(r_n[0] if r_n else {}, ("title",), "…")
    wn_t = first_field(r_w[0] if r_w else {}, ("title",), "…")
    news_line = f"{nh_t}／{wn_t}"

    r_z = _rows(z)
    r_j = _rows(jpc)
    zt = first_field(r_z[0] if r_z else {}, ("title",), "…")
    jt = first_field(r_j[0] if r_j else {}, ("title",), "…")
    jt = re.sub(r"^Weekly Report:\s*", "WR ", jt, flags=re.I)
    tech_line = f"{zt}／{jt}"

    r_m = _rows(mj)
    r_mv = _rows(mov)
    mt = first_field(r_m[0] if r_m else {}, ("title",), "…")
    movie_t = first_field(r_mv[0] if r_mv else {}, ("title", "original_title"), "…")
    ent_line = f"{mt}／{movie_t}"

    def ln(n: str, inner: str, tail: str, inner_max: int) -> str:
        return f"{n} {clip(inner, inner_max)}{tail}"

    lines = [
        f"【{d}】今日の5つ（JP）",
        ln("①", g_line, "（Google）", 24),
        ln("②", yt, "（YouTube）", 26),
        ln("③", news_line, "（NHK・WN）", 22),
        ln("④", tech_line, "（Tech）", 22),
        ln("⑤", ent_line, "（Apple Music・映画）", 20),
        "一覧: https://trends-dashboard.fly.dev/",
    ]
    return "\n".join(lines)


def build_us_block(base: str, d: str) -> str:
    gus = fetch(base, "/api/google-trends?country=US&force_refresh=false")
    cnn = fetch(base, "/api/cnn-trends?force_refresh=false")
    hn = fetch(base, "/api/hackernews-trends?force_refresh=false")
    cisa = fetch(base, "/api/cisa-kev-trends?force_refresh=false")
    dev = fetch(base, "/api/devto-trends?force_refresh=false")
    thn = fetch(base, "/api/thehackernews-trends?force_refresh=false")
    mus = fetch(base, "/api/music-trends?service=spotify&region=US&force_refresh=false")
    mov = fetch(base, "/api/movie-trends?country=US&force_refresh=false")

    r_g = _rows(gus)
    k1 = first_field(r_g[0] if r_g else {}, ("keyword",), "…")
    k2 = second_keyword(r_g)
    g_line = f"{k1} / {k2}" if k2 else k1

    r_c = _rows(cnn)
    cnn_t = first_field(r_c[0] if r_c else {}, ("title",), "…")

    r_h = _rows(hn)
    hn_t = first_field(r_h[0] if r_h else {}, ("title",), "…")

    r_ci = _rows(cisa)
    r_d = _rows(dev)
    r_t = _rows(thn)
    cve = first_field(r_ci[0] if r_ci else {}, ("cve_id",), "")
    dev_t = first_field(r_d[0] if r_d else {}, ("title",), "")
    th_short = first_field(r_t[0] if r_t else {}, ("title",), "")
    core_a = f"{cve} · DEV · {dev_t}".strip()
    core_b = f"{cve} · THN · {th_short}".strip()
    tech_core = core_a if len(core_a) <= len(core_b) else core_b

    r_m = _rows(mus)
    r_mv = _rows(mov)
    mt = first_field(r_m[0] if r_m else {}, ("title",), "…")
    mv = first_field(r_mv[0] if r_mv else {}, ("title", "original_title"), "…")
    ent_line = f"{mt} / {mv}"

    def ln(n: str, inner: str, tail: str, inner_max: int) -> str:
        return f"{n} {clip(inner, inner_max)}{tail}"

    lines = [
        f"Today's 5 (US) {d} · 8pm JST, same as JP (~US AM)",
        ln("①", g_line, " (Google)", 22),
        ln("②", cnn_t, " (CNN)", 26),
        ln("③", hn_t, " (HN)", 22),
        ln("④", tech_core, " (Tech)", 28),
        ln("⑤", ent_line, " (Apple Music)", 16),
        "https://trends-dashboard.fly.dev/",
    ]
    body = "\n".join(lines)
    if len(body) > 280:
        lines[4] = ln("④", tech_core, " (Tech)", 22)
        lines[5] = ln("⑤", ent_line, " (Apple Music)", 12)
        body = "\n".join(lines)
    if len(body) > 280:
        lines[2] = ln("②", cnn_t, " (CNN)", 22)
        lines[3] = ln("③", hn_t, " (HN)", 18)
        body = "\n".join(lines)
    return body


def substitute_fenced_section(section: str, jp_inner: str, us_inner: str) -> str:
    jp_pat = r"(### JP — 今日の5つ\n\n```\n)(.*?)(\n```)"
    us_pat = r"(### US — 今日の5つ(?:（英語・同時刻前提）)?\n\n```\n)(.*?)(\n```)"

    def jp_sub(m: re.Match[str]) -> str:
        return m.group(1) + jp_inner + m.group(3)

    def us_sub(m: re.Match[str]) -> str:
        return m.group(1) + us_inner + m.group(3)

    out, n_jp = re.subn(jp_pat, jp_sub, section, count=1, flags=re.DOTALL)
    if n_jp != 1:
        raise ValueError("JP fenced block not found or not unique in section")
    out, n_us = re.subn(us_pat, us_sub, out, count=1, flags=re.DOTALL)
    if n_us != 1:
        raise ValueError("US fenced block not found or not unique in section")
    return out


def replace_or_insert(content: str, date: str, jp_inner: str, us_inner: str) -> str:
    marker = f"## {date}\n"
    idx = content.find(marker)
    if idx < 0:
        block = f"""---

## {date}

### JP — 今日の5つ

```
{jp_inner}
```

### US — 今日の5つ（英語・同時刻前提）

```
{us_inner}
```
"""
        ins = content.find(f"\n{ANCHOR_HEADING}")
        if ins < 0:
            raise ValueError(f"Cannot find anchor {ANCHOR_HEADING!r} to append new date")
        return content[:ins] + block + content[ins:]

    next_h = content.find("\n## ", idx + 1)
    anchor = content.find(f"\n{ANCHOR_HEADING}", idx + 1)
    candidates = [x for x in (next_h, anchor) if x >= 0]
    end = min(candidates) if candidates else len(content)
    section = content[idx:end]
    new_section = substitute_fenced_section(section, jp_inner, us_inner)
    return content[:idx] + new_section + content[end:]


def default_date_jst() -> str:
    return datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", help="YYYY-MM-DD (default: today JST)")
    p.add_argument(
        "--series-file",
        default=SERIES_REL,
        help="Path to daily_series markdown (repo-relative or absolute)",
    )
    p.add_argument("--base-url", default=None, help="Override TREND_DASHBOARD_BASE_URL")
    p.add_argument("--dry-run", action="store_true", help="Print blocks only; do not write")
    p.add_argument("--write", action="store_true", help="Update series file")
    args = p.parse_args()

    import os

    base = (args.base_url or os.environ.get("TREND_DASHBOARD_BASE_URL") or BASE_DEFAULT).rstrip("/")
    d = args.date or default_date_jst()

    try:
        jp = build_jp_block(base, d)
        us = build_us_block(base, d)
    except (
        requests.RequestException,
        TimeoutError,
        json.JSONDecodeError,
        ValueError,
    ) as e:
        print(f"ERROR: fetch failed: {e}", file=sys.stderr)
        return 1

    print("=== JP ===\n")
    print(jp)
    print("\n=== US ===\n")
    print(us)
    print(f"\n(JP len={len(jp)}, US len={len(us)})")

    if args.dry_run:
        print("\n(dry-run: not writing file)", file=sys.stderr)
        return 0
    if not args.write:
        print("\n(pass --write to save)", file=sys.stderr)
        return 0

    path = args.series_file
    with open(path, encoding="utf-8") as f:
        content = f.read()
    new_content = replace_or_insert(content, d, jp, us)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"\nWrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
