#!/usr/bin/env python3
"""
Fill ``docs/x_post_samples/daily_series_from_2026-05-09.md`` for a given date.

**Preferred:** read ``trend_daily_snapshots`` for slots **07 / 13 / 19** (JST) via
``DATABASE_URL``. Labels are scored by **slot coverage** (same keyword in more slots =
higher) plus **rank improvement** from morning→afternoon→evening (lower rank number =
better). No extra upstream API traffic from this script.

**Fallback:** public Trend Dashboard JSON APIs with ``force_refresh`` query param
(use ``--from-api`` when ``DATABASE_URL`` is set but HTTP を使いたいとき).

  export DATABASE_URL=...
  python scripts/generate_daily_x_post_series.py --write

  python scripts/generate_daily_x_post_series.py --from-api --write --no-force-refresh

Env:
  DATABASE_URL        PostgreSQL（スナップショット読み取り。CI で推奨）
  TREND_DASHBOARD_BASE_URL  HTTP フォールバック用ベース URL（既定: https://trends-dashboard.fly.dev）

JP / US ともデフォルトで X 無料枠（加重カウント合計 280 相当）に収める。
JP は east_asian_width の Wide/Full を 2、その他を 1 とする近似。末尾 URL は 23 相当。
長めのコピー用（JP の加重チェックなし・US は生文字数）の例:
  python scripts/generate_daily_x_post_series.py --jp-max-x-weighted 0 --max-us-chars 500
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from typing import Any, Callable
from unicodedata import east_asian_width
from zoneinfo import ZoneInfo

import psycopg2
import requests
from psycopg2.extras import RealDictCursor

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> None:
        return None


BASE_DEFAULT = "https://trends-dashboard.fly.dev"
SERIES_REL = "docs/x_post_samples/daily_series_from_2026-05-09.md"
ANCHOR_HEADING = "## この先の日付を足すとき"
DEFAULT_JP_INNER_MAX = 200
X_FREE_CHARACTER_LIMIT = 280
DEFAULT_MAX_US_CHARS = X_FREE_CHARACTER_LIMIT
X_FREE_URL_WEIGHT = 23
POST_FOOTER_URL = "https://trends-dashboard.fly.dev/"
JP_LIST_LINE = f"一覧: {POST_FOOTER_URL}"

JP_CATEGORY_TAILS = ("（検索）", "（動画）", "（ニュース）", "（IT）", "（エンタメ）")
US_CATEGORY_TAILS = (" (Search)", " (Video)", " (News)", " (IT)", " (Entertainment)")

# スケジューラ 7時・13時・19時（JST）のスナップショットだけをマージして選定する
SNAPSHOT_SLOTS_DAYTIME = ("07", "13", "19")

# 選定スコア: 複数スロットに出たラベルを優先し、順位が上がった（数値が小さくなった）ほど加点
FREQ_WEIGHT = 10.0
JUMP_WEIGHT = 1.0


def _char_x_weight(ch: str) -> int:
    return 2 if east_asian_width(ch) in ("F", "W") else 1


def _jp_body_x_weight(body: str) -> int:
    if POST_FOOTER_URL not in body:
        return sum(_char_x_weight(c) for c in body)
    base = body.replace(POST_FOOTER_URL, "")
    return sum(_char_x_weight(c) for c in base) + X_FREE_URL_WEIGHT


def _fr_q(force_refresh: bool) -> str:
    return "true" if force_refresh else "false"


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
    cut = max_len - 1
    chunk = s[:cut]
    if " " in chunk:
        last_sp = chunk.rfind(" ")
        if last_sp > max(cut // 3, 6):
            chunk = chunk[:last_sp]
    return chunk + "…"


def second_keyword(rows: list) -> str:
    if len(rows) < 2:
        return ""
    return first_field(rows[1], ("keyword", "title"))


def _snap_text(items: list, idx: int, default: str = "…") -> str:
    if idx >= len(items) or not isinstance(items[idx], dict):
        return default
    t = items[idx].get("t")
    return str(t).strip() if t is not None and str(t).strip() else default


def _google_line_snapshot(items: list[Any], *, sep: str) -> str:
    """スナップショット items（t のみ）から Google ①行相当。"""
    k1 = _snap_text(items, 0)
    if len(items) < 2:
        return k1
    t2 = items[1].get("t") if isinstance(items[1], dict) else None
    k2 = str(t2).strip() if t2 is not None and str(t2).strip() else ""
    return f"{k1}{sep}{k2}" if k2 else k1


def normalize_label_key(t: str) -> str:
    """同一トレンド判定用のざっくり正規化（完全一致に寄せつつ空白は潰す）。"""
    return re.sub(r"\s+", " ", str(t).strip()).lower()[:600]


def _agg_primary_display(agg: dict[str, Any]) -> str:
    dbs = agg.get("display_by_slot") or {}
    for sp in ("19", "13", "07"):
        if sp in dbs:
            return str(dbs[sp])
    return "…"


def rank_jump_score(ranks: dict[str, int]) -> float:
    """
    順位は数値が小さいほど上位。07→13→19 で順位が下がれば（数値が減れば）プラス。
    13 が無い場合は 07→19 のNetのみ。
    """
    r7 = ranks.get("07")
    r13 = ranks.get("13")
    r19 = ranks.get("19")
    s = 0.0
    if r7 is not None and r13 is not None:
        s += max(0.0, float(r7 - r13))
    if r13 is not None and r19 is not None:
        s += max(0.0, float(r13 - r19))
    if r7 is not None and r19 is not None and r13 is None:
        s += max(0.0, float(r7 - r19))
    return s


def aggregate_labels_for_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
) -> dict[str, dict[str, Any]]:
    """同一 series の全スロット items をラベルキーでまとめる。"""
    out: dict[str, dict[str, Any]] = {}
    for slot in SNAPSHOT_SLOTS_DAYTIME:
        bucket = series_by_slot.get(slot) or {}
        items = bucket.get(series_key) or []
        for it in items:
            if not isinstance(it, dict):
                continue
            raw_t = it.get("t")
            if raw_t is None or not str(raw_t).strip():
                continue
            display = str(raw_t).strip()
            nk = normalize_label_key(display)
            r_raw = it.get("r")
            try:
                r = int(r_raw)
            except (TypeError, ValueError):
                r = 999
            agg = out.get(nk)
            if agg is None:
                agg = {"display_by_slot": {}, "ranks": {}}
                out[nk] = agg
            agg["display_by_slot"][slot] = display
            prev = agg["ranks"].get(slot)
            if prev is None or r < prev:
                agg["ranks"][slot] = r
    return out


def combined_label_score(agg: dict[str, Any]) -> float:
    ranks = agg.get("ranks") or {}
    freq = len(set(ranks.keys()) & set(SNAPSHOT_SLOTS_DAYTIME))
    jump = rank_jump_score(ranks)
    return FREQ_WEIGHT * float(freq) + JUMP_WEIGHT * jump


def sorted_label_displays(aggs: dict[str, dict[str, Any]]) -> list[str]:
    """スコア降順。同点は 19 時の順位が良いもの、それも同ならキー順。"""
    items = list(aggs.items())

    def sort_key(it: tuple[str, dict[str, Any]]):
        nk, agg = it
        score = combined_label_score(agg)
        r19 = (agg.get("ranks") or {}).get("19", 999)
        return (-score, r19, nk)

    items.sort(key=sort_key)
    return [_agg_primary_display(agg) for _, agg in items]


def pick_top_labels(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    *,
    count: int,
) -> list[str]:
    aggs = aggregate_labels_for_series(series_by_slot, series_key)
    displays = sorted_label_displays(aggs)
    out: list[str] = []
    seen: set[str] = set()
    for d in displays:
        if d == "…" or not d:
            continue
        sk = normalize_label_key(d)
        if sk in seen:
            continue
        seen.add(sk)
        out.append(d)
        if len(out) >= count:
            break
    return out


def google_line_from_slots(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    *,
    sep: str,
) -> str:
    picks = pick_top_labels(series_by_slot, series_key, count=2)
    if len(picks) >= 2:
        return f"{picks[0]}{sep}{picks[1]}"
    if len(picks) == 1:
        return picks[0]
    return "…"


def pick_single_line(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    *,
    postprocess: Callable[[str], str] | None = None,
) -> str:
    picks = pick_top_labels(series_by_slot, series_key, count=1)
    if not picks:
        return "…"
    s = picks[0]
    if postprocess:
        s = postprocess(s)
    return s


def load_snapshots_daytime_slots(
    database_url: str,
    business_day: date,
    *,
    connect_timeout: int = 15,
) -> dict[str, dict[str, list[Any]]]:
    """
    business_day の 07 / 13 / 19 スロットをすべて読み、
    ``{ slot: { series_key: items } }`` を返す。
    """
    out: dict[str, dict[str, list[Any]]] = {s: {} for s in SNAPSHOT_SLOTS_DAYTIME}
    conn = psycopg2.connect(database_url, connect_timeout=connect_timeout)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT slot, series_key, items
                FROM trend_daily_snapshots
                WHERE business_day = %s AND slot IN ('07','13','19')
                ORDER BY slot, series_key
                """,
                (business_day,),
            )
            rows = cur.fetchall()
            for row in rows:
                slot = str(row.get("slot") or "")
                if slot not in out:
                    continue
                sk = row.get("series_key")
                items = row.get("items")
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except json.JSONDecodeError:
                        items = []
                if not isinstance(items, list):
                    items = []
                out[slot][str(sk)] = items
    finally:
        conn.close()

    if all(len(out[s]) == 0 for s in SNAPSHOT_SLOTS_DAYTIME):
        raise ValueError(
            f"No trend_daily_snapshots for business_day={business_day.isoformat()} "
            f"in slots {', '.join(SNAPSHOT_SLOTS_DAYTIME)}"
        )
    return out


def _compose_jp_body(
    d: str,
    *,
    g_line: str,
    yt: str,
    news_line: str,
    tech_line: str,
    ent_line: str,
    inner_max: int,
    max_jp_x_weighted: int,
) -> str:
    def ln(n: str, inner: str, tail: str, lim: int) -> str:
        return f"{n} {clip(inner, lim)}{tail}"

    im = max(8, inner_max)
    body = ""
    while im >= 4:
        lines = [
            f"【{d}】今日の5つ（JP）",
            ln("①", g_line, JP_CATEGORY_TAILS[0], im),
            ln("②", yt, JP_CATEGORY_TAILS[1], im),
            ln("③", news_line, JP_CATEGORY_TAILS[2], im),
            ln("④", tech_line, JP_CATEGORY_TAILS[3], im),
            ln("⑤", ent_line, JP_CATEGORY_TAILS[4], im),
            JP_LIST_LINE,
        ]
        body = "\n".join(lines)
        if max_jp_x_weighted <= 0 or _jp_body_x_weight(body) <= max_jp_x_weighted:
            break
        im -= 2
    if max_jp_x_weighted > 0 and _jp_body_x_weight(body) > max_jp_x_weighted:
        print(
            "WARNING: JP block still exceeds X weighted budget; tighten sources or post as thread",
            file=sys.stderr,
        )
    return body


def build_jp_block_from_snapshots(
    series_by_slot: dict[str, dict[str, list[Any]]],
    d: str,
    inner_max: int = DEFAULT_JP_INNER_MAX,
    *,
    max_jp_x_weighted: int = X_FREE_CHARACTER_LIMIT,
) -> str:
    g_line = google_line_from_slots(series_by_slot, "google_trends_jp", sep="／")

    yt = pick_single_line(series_by_slot, "youtube_trends_jp")
    nh_t = pick_single_line(series_by_slot, "nhk_jp")
    wn_t = pick_single_line(series_by_slot, "worldnews_jp")
    news_line = f"{nh_t}／{wn_t}"

    zt = pick_single_line(series_by_slot, "zenn_jp")
    jt = pick_single_line(
        series_by_slot,
        "jpcert_jp",
        postprocess=lambda s: re.sub(r"^Weekly Report:\s*", "WR ", s, flags=re.I),
    )
    tech_line = f"{zt}／{jt}"

    mt = pick_single_line(series_by_slot, "music_trends_jp")
    movie_t = pick_single_line(series_by_slot, "movie_jp")
    ent_line = f"{mt}／{movie_t}"

    return _compose_jp_body(
        d,
        g_line=g_line,
        yt=yt,
        news_line=news_line,
        tech_line=tech_line,
        ent_line=ent_line,
        inner_max=inner_max,
        max_jp_x_weighted=max_jp_x_weighted,
    )



def build_jp_block(
    base: str,
    d: str,
    inner_max: int = DEFAULT_JP_INNER_MAX,
    *,
    max_jp_x_weighted: int = X_FREE_CHARACTER_LIMIT,
    force_refresh: bool = False,
) -> str:
    fr = _fr_q(force_refresh)
    gjp = fetch(base, f"/api/google-trends?country=JP&force_refresh={fr}")
    yjp = fetch(base, f"/api/youtube-trends?region=JP&force_refresh={fr}")
    nh = fetch(base, f"/api/nhk-trends?force_refresh={fr}")
    wn = fetch(base, f"/api/worldnews-trends?country=jp&force_refresh={fr}")
    z = fetch(base, f"/api/zenn-trends?force_refresh={fr}")
    jpc = fetch(base, f"/api/jpcert-trends?force_refresh={fr}")
    mj = fetch(base, f"/api/music-trends?service=spotify&region=JP&force_refresh={fr}")
    mov = fetch(base, f"/api/movie-trends?country=JP&force_refresh={fr}")

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

    return _compose_jp_body(
        d,
        g_line=g_line,
        yt=yt,
        news_line=news_line,
        tech_line=tech_line,
        ent_line=ent_line,
        inner_max=inner_max,
        max_jp_x_weighted=max_jp_x_weighted,
    )


def _us_header(d: str, compact: bool) -> str:
    if compact:
        return f"Today's 5 (US) {d} · 8pm JST\n"
    return f"Today's 5 (US) {d} · 8pm JST, same as JP (~US AM)\n"


def _us_body_weight(body: str, *, x_free_counting: bool) -> int:
    if not x_free_counting:
        return len(body)
    if POST_FOOTER_URL not in body:
        return len(body)
    return len(body) - len(POST_FOOTER_URL) + X_FREE_URL_WEIGHT


def _us_fixed_overhead(d: str, compact_header: bool, *, x_free_counting: bool) -> int:
    header = _us_header(d, compact_header).rstrip("\n")
    url_cost = X_FREE_URL_WEIGHT if x_free_counting else len(POST_FOOTER_URL)
    parts = [
        ("① ", US_CATEGORY_TAILS[0]),
        ("② ", US_CATEGORY_TAILS[1]),
        ("③ ", US_CATEGORY_TAILS[2]),
        ("④ ", US_CATEGORY_TAILS[3]),
        ("⑤ ", US_CATEGORY_TAILS[4]),
    ]
    n = len(header) + url_cost + 6
    for pre, suf in parts:
        n += len(pre) + len(suf)
    return n


def _compose_us_body(
    d: str,
    *,
    g_line: str,
    yt_us: str,
    cnn_t: str,
    tech_core: str,
    ent_line: str,
    max_chars: int,
) -> str:
    x_free_counting = max_chars <= X_FREE_CHARACTER_LIMIT
    compact = x_free_counting
    fixed = _us_fixed_overhead(d, compact, x_free_counting=x_free_counting)

    def assemble(inner_limits: list[int]) -> list[str]:
        def ln(n: str, inner: str, tail: str, inner_max: int) -> str:
            return f"{n}{clip(inner, inner_max)}{tail}"

        return [
            _us_header(d, compact).rstrip("\n"),
            ln("① ", g_line, US_CATEGORY_TAILS[0], inner_limits[0]),
            ln("② ", yt_us, US_CATEGORY_TAILS[1], inner_limits[1]),
            ln("③ ", cnn_t, US_CATEGORY_TAILS[2], inner_limits[2]),
            ln("④ ", tech_core, US_CATEGORY_TAILS[3], inner_limits[3]),
            ln("⑤ ", ent_line, US_CATEGORY_TAILS[4], inner_limits[4]),
            POST_FOOTER_URL,
        ]

    if max_chars <= 0:
        generous = 300
        lines = assemble([generous] * 5)
        return "\n".join(lines)

    remaining = max_chars - fixed
    if remaining < 50:
        raise ValueError(f"max_us_chars={max_chars} is too small for US template (fixed overhead ~{fixed})")

    base_each = max(24, remaining // 5)
    limits = [base_each + (1 if i < (remaining % 5) else 0) for i in range(5)]

    lines = assemble(limits)
    body = "\n".join(lines)

    def over_budget(b: str) -> int:
        return _us_body_weight(b, x_free_counting=x_free_counting) - max_chars

    guard = 0
    while over_budget(body) > 0 and guard < 500:
        guard += 1
        idx = max(range(5), key=lambda i: limits[i])
        if limits[idx] <= 12:
            break
        limits[idx] = max(12, limits[idx] - max(1, min(over_budget(body), 8)))
        lines = assemble(limits)
        body = "\n".join(lines)

    return body


def build_us_block_from_snapshots(
    series_by_slot: dict[str, dict[str, list[Any]]],
    d: str,
    max_chars: int = DEFAULT_MAX_US_CHARS,
) -> str:
    g_line = google_line_from_slots(series_by_slot, "google_trends_us", sep=" / ")

    yt_us = pick_single_line(series_by_slot, "youtube_trends_us")
    cnn_t = pick_single_line(series_by_slot, "cnn_us")

    cve = pick_single_line(series_by_slot, "cisa_kev_us")
    dev_t = pick_single_line(series_by_slot, "devto_us")
    th_short = pick_single_line(series_by_slot, "thehackernews_us")
    core_a = f"{cve} · DEV · {dev_t}".strip()
    core_b = f"{cve} · THN · {th_short}".strip()
    tech_core = core_a if len(core_a) <= len(core_b) else core_b

    mt = pick_single_line(series_by_slot, "music_trends_us")
    mv = pick_single_line(series_by_slot, "movie_us")
    ent_line = f"{mt} / {mv}"

    return _compose_us_body(
        d,
        g_line=g_line,
        yt_us=yt_us,
        cnn_t=cnn_t,
        tech_core=tech_core,
        ent_line=ent_line,
        max_chars=max_chars,
    )


def build_us_block(
    base: str,
    d: str,
    max_chars: int = DEFAULT_MAX_US_CHARS,
    *,
    force_refresh: bool = False,
) -> str:
    fr = _fr_q(force_refresh)
    gus = fetch(base, f"/api/google-trends?country=US&force_refresh={fr}")
    yus = fetch(base, f"/api/youtube-trends?region=US&force_refresh={fr}")
    cnn = fetch(base, f"/api/cnn-trends?force_refresh={fr}")
    cisa = fetch(base, f"/api/cisa-kev-trends?force_refresh={fr}")
    dev = fetch(base, f"/api/devto-trends?force_refresh={fr}")
    thn = fetch(base, f"/api/thehackernews-trends?force_refresh={fr}")
    mus = fetch(base, f"/api/music-trends?service=spotify&region=US&force_refresh={fr}")
    mov = fetch(base, f"/api/movie-trends?country=US&force_refresh={fr}")

    r_g = _rows(gus)
    k1 = first_field(r_g[0] if r_g else {}, ("keyword",), "…")
    k2 = second_keyword(r_g)
    g_line = f"{k1} / {k2}" if k2 else k1

    r_yu = _rows(yus)
    yt_us = first_field(r_yu[0] if r_yu else {}, ("title",), "…")

    r_c = _rows(cnn)
    cnn_t = first_field(r_c[0] if r_c else {}, ("title",), "…")

    r_ci = _rows(cisa)
    r_d = _rows(dev)
    r_t = _rows(thn)
    cve = first_field(r_ci[0] if r_ci else {}, ("cve_id",), "")
    if not cve:
        cve = first_field(r_ci[0] if r_ci else {}, ("title",), "")
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

    return _compose_us_body(
        d,
        g_line=g_line,
        yt_us=yt_us,
        cnn_t=cnn_t,
        tech_core=tech_core,
        ent_line=ent_line,
        max_chars=max_chars,
    )


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
    load_dotenv()

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", help="YYYY-MM-DD (default: today JST) — business_day for snapshots")
    p.add_argument(
        "--series-file",
        default=SERIES_REL,
        help="Path to daily_series markdown (repo-relative or absolute)",
    )
    p.add_argument("--base-url", default=None, help="Override TREND_DASHBOARD_BASE_URL (HTTP mode)")
    p.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for trend_daily_snapshots",
    )
    p.add_argument(
        "--from-api",
        action="store_true",
        help="Use HTTP JSON APIs instead of DATABASE_URL (even if DATABASE_URL is set)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print blocks only; do not write")
    p.add_argument("--write", action="store_true", help="Update series file")
    fr = p.add_mutually_exclusive_group()
    fr.add_argument(
        "--force-refresh",
        action="store_true",
        help="HTTP mode only: force_refresh=true on all /api calls",
    )
    fr.add_argument(
        "--no-force-refresh",
        action="store_true",
        help="HTTP mode only: force_refresh=false (dashboard cache)",
    )
    p.add_argument(
        "--jp-inner-max",
        type=int,
        default=DEFAULT_JP_INNER_MAX,
        help=f"Starting max chars per JP line inner before X-weight trim (default: {DEFAULT_JP_INNER_MAX})",
    )
    p.add_argument(
        "--jp-max-x-weighted",
        type=int,
        default=X_FREE_CHARACTER_LIMIT,
        help=(
            "JP block X-style weighted budget (default "
            f"{X_FREE_CHARACTER_LIMIT}; Wide/Full=2 else 1; URL≈{X_FREE_URL_WEIGHT}; 0=no cap)"
        ),
    )
    p.add_argument(
        "--max-us-chars",
        type=int,
        default=DEFAULT_MAX_US_CHARS,
        help=(
            "US block budget: default "
            f"{DEFAULT_MAX_US_CHARS} (X free tier; footer URL counted as ~{X_FREE_URL_WEIGHT}). "
            f"Above {X_FREE_CHARACTER_LIMIT}, raw character length is used. "
            "0 = no budget, lines capped at 300."
        ),
    )
    args = p.parse_args()

    d = args.date or default_date_jst()
    try:
        business_day = date.fromisoformat(d)
    except ValueError:
        print(f"ERROR: invalid --date {d!r} (expected YYYY-MM-DD)", file=sys.stderr)
        return 1

    database_url = (args.database_url or os.environ.get("DATABASE_URL") or "").strip()
    use_snapshots = bool(database_url) and not args.from_api

    if use_snapshots:
        try:
            series_by_slot = load_snapshots_daytime_slots(database_url, business_day)
        except (ValueError, psycopg2.Error) as e:
            print(f"ERROR: snapshot load failed: {e}", file=sys.stderr)
            return 1
        print(
            f"Source: trend_daily_snapshots slots={'/'.join(SNAPSHOT_SLOTS_DAYTIME)} "
            f"business_day={d} (DATABASE_URL); scores=freq×{FREQ_WEIGHT}+jump×{JUMP_WEIGHT}",
            file=sys.stderr,
        )
        try:
            jp = build_jp_block_from_snapshots(
                series_by_slot,
                d,
                inner_max=args.jp_inner_max,
                max_jp_x_weighted=args.jp_max_x_weighted,
            )
            us = build_us_block_from_snapshots(series_by_slot, d, max_chars=args.max_us_chars)
        except ValueError as e:
            print(f"ERROR: compose failed: {e}", file=sys.stderr)
            return 1
    else:
        base = (args.base_url or os.environ.get("TREND_DASHBOARD_BASE_URL") or BASE_DEFAULT).rstrip(
            "/"
        )
        if args.force_refresh:
            force_refresh = True
        elif args.no_force_refresh:
            force_refresh = False
        else:
            force_refresh = False
        print(
            f"Source: HTTP {base} force_refresh={force_refresh}",
            file=sys.stderr,
        )
        try:
            jp = build_jp_block(
                base,
                d,
                inner_max=args.jp_inner_max,
                max_jp_x_weighted=args.jp_max_x_weighted,
                force_refresh=force_refresh,
            )
            us = build_us_block(base, d, max_chars=args.max_us_chars, force_refresh=force_refresh)
        except (
            requests.RequestException,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
        ) as e:
            print(f"ERROR: HTTP fetch failed: {e}", file=sys.stderr)
            return 1

    print("=== JP ===\n")
    print(jp)
    print("\n=== US ===\n")
    print(us)
    jp_xw = _jp_body_x_weight(jp)
    us_raw = len(us)
    us_xcount = _us_body_weight(us, x_free_counting=True)
    print(f"\n(JP len={len(jp)}, JP X-weight≈{jp_xw}, US raw len={us_raw}, US X-count≈{us_xcount})")

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
