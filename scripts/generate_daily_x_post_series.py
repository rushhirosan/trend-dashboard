#!/usr/bin/env python3
"""
Writes **one Markdown file per calendar day** under ``docs/x_post_samples/daily/{YYYY-MM-DD}.md``
(same JP/US fenced layout as before).

**Preferred:** read ``trend_daily_snapshots`` for slots **07 / 13 / 19** (JST) via
``DATABASE_URL``. Labels are scored by **slot coverage** (same keyword in more slots =
higher) plus **rank improvement** from morning→afternoon→evening (lower rank number =
better). No extra upstream API traffic from this script.

**Fly / CI (no direct DB):** ``--from-api`` reads the same rows as the AI daily summary:
``GET /api/summaries/daily-snapshots?business_day=…`` (``trend_daily_snapshots``, slots 07/13/19),
then composes JP/US blocks. No per-source ``/api/google-trends`` traffic.

**business_day (default):** JST ``now − 12h`` の暦日（夕方 X 投稿向け）。GHA schedule が
翌未明まで遅れても **実行日ではなく観測日** の 07/13/19 を読む。上書きは ``--date YYYY-MM-DD``。

**Legacy per-source HTTP** (no ``DATABASE_URL`` and **without** ``--from-api``): each
``/api/*`` with ``force_refresh`` (default false).

  export DATABASE_URL=...
  python scripts/generate_daily_x_post_series.py --write

  python scripts/generate_daily_x_post_series.py --from-api --write

  python scripts/generate_daily_x_post_series.py --from-api --write --discord

Env:
  DATABASE_URL             直接 PostgreSQL から 07/13/19 を読む（``--from-api`` なしのとき）
  TREND_DASHBOARD_BASE_URL ``--from-api`` またはレガシー HTTP 用ベース URL（既定: https://trends-dashboard.fly.dev）
  DISCORD_WEBHOOK_URL       ``--discord`` 用（スケジューラ通知と同じ Webhook）

夜の X 文案は **急上昇3つ**（07→13→19・AI 日次サマリーと同じ jump / 資格 / ノイズ判定。
全ソースから最大3件）。JP / US とも X 無料枠（加重 280 相当）に収める。
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
import time
from datetime import date, datetime, timedelta
from pathlib import Path
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

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import snapshot_rising as sr

BASE_DEFAULT = "https://trends-dashboard.fly.dev"
DEFAULT_OUTPUT_DIR = "docs/x_post_samples/daily"
DEFAULT_JP_INNER_MAX = 200
X_FREE_CHARACTER_LIMIT = 280
DEFAULT_MAX_US_CHARS = X_FREE_CHARACTER_LIMIT
X_FREE_URL_WEIGHT = 23
POST_FOOTER_URL = "https://trends-dashboard.fly.dev/"
POST_FOOTER_URL_US = "https://trends-dashboard.fly.dev/us"
JP_LIST_LINE = f"全ソース: {POST_FOOTER_URL}"
US_LIST_LINE = f"Dashboard: {POST_FOOTER_URL_US}"

JP_CATEGORY_TAILS = ("（検索）", "（動画）", "（ニュース）", "（IT）", "（エンタメ）")
US_CATEGORY_TAILS = (" (Search)", " (Video)", " (News)", " (IT)", " (Entertainment)")

# 夜の X 投稿: 07→13→19 で順位が上がったラベルを全ソース横断で最大3件
RISING_PICK_COUNT = 3
RISING_MARKERS = ("①", "②", "③")

JP_SERIES_KEYS = (
    "google_trends_jp",
    "youtube_trends_jp",
    "nhk_jp",
    "worldnews_jp",
    "zenn_jp",
    "jpcert_jp",
    "music_trends_jp",
    "movie_jp",
)
US_SERIES_KEYS = (
    "google_trends_us",
    "youtube_trends_us",
    "cnn_us",
    "cisa_kev_us",
    "devto_us",
    "thehackernews_us",
    "music_trends_us",
    "movie_us",
)

SERIES_CATEGORY_JP: dict[str, str] = {
    "google_trends_jp": "検索",
    "youtube_trends_jp": "動画",
    "nhk_jp": "ニュース",
    "worldnews_jp": "ニュース",
    "zenn_jp": "IT",
    "jpcert_jp": "IT",
    "music_trends_jp": "エンタメ",
    "movie_jp": "エンタメ",
}
SERIES_CATEGORY_US: dict[str, str] = {
    "google_trends_us": "Search",
    "youtube_trends_us": "Video",
    "cnn_us": "News",
    "cisa_kev_us": "IT",
    "devto_us": "IT",
    "thehackernews_us": "IT",
    "music_trends_us": "Entertainment",
    "movie_us": "Entertainment",
}

# スケジューラ 7時・13時・19時（JST）のスナップショットだけをマージして選定する
SNAPSHOT_SLOTS_DAYTIME = sr.DAYTIME_SLOTS

# 選定スコア: 複数スロットに出たラベルを優先し、順位が上がった（数値が小さくなった）ほど加点
FREQ_WEIGHT = 10.0
JUMP_WEIGHT = 1.0


_snapshot_top_n = sr.snapshot_top_n
_rank_out_of_range = sr.rank_out_of_range
rank_jump_score = sr.rank_jump_score
rising_qualifies = sr.rising_qualifies
normalize_label_key = sr.normalize_label_key
clean_rising_display = sr.clean_rising_display
is_weak_rising_label = sr.is_weak_rising_label
is_noisy_label = sr.is_noisy_label


def _char_x_weight(ch: str) -> int:
    return 2 if east_asian_width(ch) in ("F", "W") else 1


def _jp_body_x_weight(body: str) -> int:
    if POST_FOOTER_URL not in body:
        return sum(_char_x_weight(c) for c in body)
    base = body.replace(POST_FOOTER_URL, "")
    return sum(_char_x_weight(c) for c in base) + X_FREE_URL_WEIGHT


def _us_body_x_weight(body: str) -> int:
    if US_LIST_LINE in body:
        base = body.replace(US_LIST_LINE, "")
        return sum(_char_x_weight(c) for c in base) + X_FREE_URL_WEIGHT
    if POST_FOOTER_URL_US in body:
        base = body.replace(POST_FOOTER_URL_US, "")
        return sum(_char_x_weight(c) for c in base) + X_FREE_URL_WEIGHT
    if POST_FOOTER_URL in body:
        base = body.replace(POST_FOOTER_URL, "")
        return sum(_char_x_weight(c) for c in base) + X_FREE_URL_WEIGHT
    return sum(_char_x_weight(c) for c in body)


def _us_footer_line_cost(*, x_free_counting: bool) -> int:
    if x_free_counting:
        return _us_body_x_weight(US_LIST_LINE)
    return len(US_LIST_LINE)


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


def _format_rising_date_short(d: str) -> str:
    """YYYY-MM-DD → M/D（X 向け短い日付）。"""
    parts = d.split("-")
    if len(parts) == 3:
        try:
            return f"{int(parts[1])}/{int(parts[2])}"
        except ValueError:
            pass
    return d


def _jp_rising_header(d: str, *, compact: bool, count: int) -> str:
    if compact:
        return f"【{_format_rising_date_short(d)}】急上昇{count}（JP）"
    return f"【{d}】今日の急上昇3つ（JP）"


def _us_rising_header(d: str, *, compact: bool, count: int) -> str:
    if compact:
        return f"Rising {count} (US) {_format_rising_date_short(d)} · 8pm JST"
    return f"Today's rising 3 (US) {d} · 8pm JST"


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


def _agg_primary_display(agg: dict[str, Any]) -> str:
    dbs = agg.get("display_by_slot") or {}
    for sp in ("19", "13", "07"):
        if sp in dbs:
            return str(dbs[sp])
    return "…"


def aggregate_labels_for_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
) -> dict[str, dict[str, Any]]:
    return sr.aggregate_labels_for_series(series_by_slot, series_key)


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


def _postprocess_series_display(series_key: str, display: str) -> str:
    if series_key == "jpcert_jp":
        return re.sub(r"^Weekly Report:\s*", "WR ", display, flags=re.I)
    return display


def pick_rising_topics(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_keys: tuple[str, ...],
    *,
    category_by_series: dict[str, str],
    count: int = RISING_PICK_COUNT,
    include_article_links: bool = True,
) -> list[tuple[str, str, str]]:
    """
    急上昇（AI 日次サマリーと同じ jump / 資格 / ノイズ判定）を最大 count 件。
    各要素は (表示ラベル, カテゴリ, 記事URL)。足りないときは「…」で埋める。
    """
    candidates = sr.collect_rising_candidates(
        series_by_slot,
        series_keys,
        display_postprocess=_postprocess_series_display,
        tail_for_series=lambda sk: category_by_series.get(sk, "他"),
    )
    items = sr.pick_top_rising(candidates, count=count)
    if len(items) < count:
        print(
            f"NOTE: only {len(items)} qualified rising label(s) (target {count})",
            file=sys.stderr,
        )
    out: list[tuple[str, str, str]] = []
    for c in items:
        sk = str(c.get("series_key") or "")
        display = str(c["display"])
        tail = str(c.get("tail") or category_by_series.get(sk, "他"))
        url = (
            sr.article_url_for_rising(series_by_slot, sk, display)
            if include_article_links
            else ""
        )
        out.append((display, tail, url))
    fallback_tail = next(iter(category_by_series.values()), "他")
    while len(out) < count:
        out.append(("…", fallback_tail, ""))
    return out[:count]


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

    _validate_daytime_snapshot_bundle(out, business_day)
    return out


def _parse_snapshot_rows_into_bundle(
    rows: list[Any],
) -> dict[str, dict[str, list[Any]]]:
    out: dict[str, dict[str, list[Any]]] = {s: {} for s in SNAPSHOT_SLOTS_DAYTIME}
    for row in rows:
        if not isinstance(row, dict):
            continue
        slot = str(row.get("slot") or "")
        if slot not in out:
            continue
        sk = row.get("series_key")
        if sk is None or not str(sk).strip():
            continue
        items = row.get("items")
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except json.JSONDecodeError:
                items = []
        if not isinstance(items, list):
            items = []
        out[slot][str(sk)] = items
    return out


def _missing_snapshot_slots(
    out: dict[str, dict[str, list[Any]]],
    required_slots: tuple[str, ...],
) -> list[str]:
    return [s for s in required_slots if len(out.get(s, {})) == 0]


def _validate_daytime_snapshot_bundle(
    out: dict[str, dict[str, list[Any]]],
    business_day: date,
    *,
    required_slots: tuple[str, ...] | None = None,
) -> None:
    if all(len(out[s]) == 0 for s in SNAPSHOT_SLOTS_DAYTIME):
        raise ValueError(
            f"No trend_daily_snapshots for business_day={business_day.isoformat()} "
            f"in slots {', '.join(SNAPSHOT_SLOTS_DAYTIME)}"
        )
    if not required_slots:
        return
    missing = _missing_snapshot_slots(out, required_slots)
    if not missing:
        return
    have = [s for s in SNAPSHOT_SLOTS_DAYTIME if len(out.get(s, {})) > 0]
    suffix = f" (have: {', '.join(have)})" if have else ""
    raise ValueError(
        f"Incomplete trend_daily_snapshots for business_day={business_day.isoformat()}: "
        f"missing slot(s) {', '.join(missing)}{suffix}"
    )


def _fetch_snapshots_daytime_bundle_from_api(
    base_url: str,
    business_day: date,
    *,
    timeout: int = 120,
) -> dict[str, dict[str, list[Any]]]:
    url = (
        f"{base_url.rstrip('/')}/api/summaries/daily-snapshots"
        f"?business_day={business_day.isoformat()}"
    )
    r = requests.get(
        url,
        headers={"User-Agent": "trend-dashboard-daily-x-post-series/1.0"},
        timeout=timeout,
    )
    r.raise_for_status()
    payload = r.json()
    if not isinstance(payload, dict) or not payload.get("success"):
        err = payload.get("error") if isinstance(payload, dict) else None
        raise RuntimeError(f"snapshot API error: {err or payload!r}")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("snapshot API: expected data array")
    return _parse_snapshot_rows_into_bundle(rows)


def load_snapshots_daytime_slots_from_api(
    base_url: str,
    business_day: date,
    *,
    timeout: int = 120,
    required_slots: tuple[str, ...] | None = None,
    wait_timeout_seconds: int = 0,
    poll_interval_seconds: int = 60,
) -> dict[str, dict[str, list[Any]]]:
    """
    ``/api/summaries/daily-snapshots`` から DB と同形の行を取り、
    ``load_snapshots_daytime_slots`` と同じ ``{ slot: { series_key: items } }`` を返す。
    スロット 01 は無視し 07/13/19 のみ詰める（DB 読みと一致）。

    ``required_slots`` 指定時は各スロットに1件以上の series があるまで待てる
    （``wait_timeout_seconds`` > 0 のときポーリング）。
    """
    required = required_slots or ()
    deadline = (
        time.monotonic() + max(0, wait_timeout_seconds)
        if wait_timeout_seconds > 0
        else None
    )
    while True:
        out = _fetch_snapshots_daytime_bundle_from_api(
            base_url, business_day, timeout=timeout
        )
        try:
            _validate_daytime_snapshot_bundle(
                out, business_day, required_slots=required or None
            )
            return out
        except ValueError as e:
            if deadline is None or time.monotonic() >= deadline:
                raise
            print(f"WAIT: {e}; retry in {poll_interval_seconds}s", file=sys.stderr)
            time.sleep(max(1, poll_interval_seconds))


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


def _compose_jp_rising_body(
    d: str,
    picks: list[tuple[str, str, str]],
    *,
    inner_max: int,
    max_jp_x_weighted: int,
    include_article_links: bool = True,
) -> str:
    compact = max_jp_x_weighted > 0
    pick_counts = (3, 2, 1) if compact else (len(picks),)

    def ln(
        marker: str,
        inner: str,
        tail: str,
        url: str,
        lim: int,
        *,
        with_links: bool,
    ) -> str:
        head = f"{marker} {clip(inner, lim)}"
        if with_links and url:
            return f"{head}\n{url}"
        return head

    def assemble(
        subset: list[tuple[str, str, str]],
        lim: int,
        *,
        with_links: bool,
    ) -> str:
        n = len(subset)
        lines = [_jp_rising_header(d, compact=compact, count=n)]
        for marker, (inner, tail, url) in zip(RISING_MARKERS, subset):
            lines.append(
                ln(marker, inner, tail, url, lim, with_links=with_links)
            )
        lines.append(JP_LIST_LINE)
        return "\n".join(lines)

    body = ""
    reduced_note = False
    dropped_links = False
    link_passes: list[bool] = [False]
    if include_article_links:
        link_passes = [True]
        if compact:
            link_passes.append(False)

    for with_links in link_passes:
        for n in pick_counts:
            subset = picks[:n]
            if not subset:
                continue
            im = 48 if compact else max(12, inner_max)
            while im >= 8:
                body = assemble(subset, im, with_links=with_links)
                if max_jp_x_weighted <= 0 or _jp_body_x_weight(body) <= max_jp_x_weighted:
                    if compact and n < len(picks) and not reduced_note:
                        print(
                            f"NOTE: JP rising reduced to {n} item(s) for X budget",
                            file=sys.stderr,
                        )
                        reduced_note = True
                    if (
                        compact
                        and include_article_links
                        and not with_links
                        and not dropped_links
                    ):
                        print(
                            "WARNING: JP rising block dropped article links to fit X budget",
                            file=sys.stderr,
                        )
                        dropped_links = True
                    return body
                im -= 2

    if max_jp_x_weighted > 0 and body and _jp_body_x_weight(body) > max_jp_x_weighted:
        print(
            "WARNING: JP rising block still exceeds X weighted budget",
            file=sys.stderr,
        )
    return body


def build_jp_block_from_snapshots(
    series_by_slot: dict[str, dict[str, list[Any]]],
    d: str,
    inner_max: int = DEFAULT_JP_INNER_MAX,
    *,
    max_jp_x_weighted: int = X_FREE_CHARACTER_LIMIT,
    include_article_links: bool = True,
) -> str:
    picks = pick_rising_topics(
        series_by_slot,
        JP_SERIES_KEYS,
        category_by_series=SERIES_CATEGORY_JP,
        count=RISING_PICK_COUNT,
        include_article_links=include_article_links,
    )
    return _compose_jp_rising_body(
        d,
        picks,
        inner_max=inner_max,
        max_jp_x_weighted=max_jp_x_weighted,
        include_article_links=include_article_links,
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
    return _us_body_x_weight(body)


def _us_fixed_overhead(d: str, compact_header: bool, *, x_free_counting: bool) -> int:
    header = _us_header(d, compact_header).rstrip("\n")
    url_cost = _us_footer_line_cost(x_free_counting=x_free_counting)
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
            US_LIST_LINE,
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


def _compose_us_rising_body(
    d: str,
    picks: list[tuple[str, str, str]],
    *,
    max_chars: int,
    include_article_links: bool = True,
) -> str:
    x_free_counting = max_chars <= X_FREE_CHARACTER_LIMIT
    compact = x_free_counting and max_chars > 0
    pick_counts = (3, 2, 1) if compact else (len(picks),)

    def ln(
        marker: str,
        inner: str,
        tail: str,
        article_url: str,
        inner_limit: int,
        *,
        with_links: bool,
    ) -> str:
        head = f"{marker} {clip(inner, inner_limit)}"
        if with_links and article_url:
            return f"{head}\n{article_url}"
        return head

    def assemble(
        subset: list[tuple[str, str, str]],
        inner_limit: int,
        *,
        with_links: bool,
    ) -> str:
        n = len(subset)
        lines = [_us_rising_header(d, compact=compact, count=n)]
        for marker, (inner, tail, article_url) in zip(RISING_MARKERS, subset):
            lines.append(
                ln(
                    marker,
                    inner,
                    tail,
                    article_url,
                    inner_limit,
                    with_links=with_links,
                )
            )
        lines.append(US_LIST_LINE)
        return "\n".join(lines)

    def over_budget(body: str) -> bool:
        if max_chars <= 0:
            return False
        if x_free_counting:
            return _us_body_x_weight(body) > max_chars
        return len(body) > max_chars

    if max_chars <= 0:
        return assemble(picks, 80, with_links=include_article_links)

    body = ""
    reduced_note = False
    dropped_links = False
    link_passes: list[bool] = [False]
    if include_article_links:
        link_passes = [True]
        if compact:
            link_passes.append(False)

    for with_links in link_passes:
        for n in pick_counts:
            subset = picks[:n]
            if not subset:
                continue
            inner_limit = 48 if compact else 48
            while inner_limit >= 8:
                body = assemble(subset, inner_limit, with_links=with_links)
                if not over_budget(body):
                    if compact and n < len(picks) and not reduced_note:
                        print(
                            f"NOTE: US rising reduced to {n} item(s) for X budget",
                            file=sys.stderr,
                        )
                        reduced_note = True
                    if (
                        compact
                        and include_article_links
                        and not with_links
                        and not dropped_links
                    ):
                        print(
                            "WARNING: US rising block dropped article links to fit X budget",
                            file=sys.stderr,
                        )
                        dropped_links = True
                    return body
                inner_limit -= 2

    if over_budget(body):
        print(
            "WARNING: US rising block still exceeds X budget; tighten sources or post as thread",
            file=sys.stderr,
        )
    return body


def build_x_post_blocks_for_discord_copy(
    series_by_slot: dict[str, dict[str, list[Any]]],
    d: str,
) -> tuple[str, str]:
    """Discord 用: X にそのまま貼る（280 字・記事 URL は収まれば付ける）。"""
    jp = build_jp_block_from_snapshots(
        series_by_slot,
        d,
        include_article_links=True,
    )
    us = build_us_block_from_snapshots(
        series_by_slot,
        d,
        include_article_links=True,
    )
    return jp, us


def build_us_block_from_snapshots(
    series_by_slot: dict[str, dict[str, list[Any]]],
    d: str,
    max_chars: int = DEFAULT_MAX_US_CHARS,
    *,
    include_article_links: bool = True,
) -> str:
    picks = pick_rising_topics(
        series_by_slot,
        US_SERIES_KEYS,
        category_by_series=SERIES_CATEGORY_US,
        count=RISING_PICK_COUNT,
        include_article_links=include_article_links,
    )
    return _compose_us_rising_body(
        d, picks, max_chars=max_chars, include_article_links=include_article_links
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


def compose_daily_markdown(date_str: str, jp_inner: str, us_inner: str) -> str:
    """Single-day file: same section shape as the former monolithic series doc."""
    lines = [
        f"# 日次 X ツイート案 — {date_str}",
        "",
        "`docs/x_post_samples/daily_guide.md` の **夜用・急上昇3つ** 型。**朝の読み物は AI 日次サマリー**（`docs/summaries/daily/`）のみ。",
        "",
        "- **自動投入:** `scripts/generate_daily_x_post_series.py --write` が **`trend_daily_snapshots`** の **07 / 13 / 19** を読み、**AI 日次サマリーと同じ急上昇判定**で全ソース横断・最大3件（JP/US 各ブロック）選びます。入力は **`DATABASE_URL`** か **`--from-api`**（`GET /api/summaries/daily-snapshots`）。",
        "- **GitHub Actions:** `.github/workflows/daily-x-post-series.yml` が **JST 20:10 前後（UTC 11:10）** に **`docs/x_post_samples/daily/{日付}.md`** を更新します。",
        f"- {JP_LIST_LINE}",
        "- 鮮度: https://trends-dashboard.fly.dev/data-status",
        "",
        "**US 返信に足す場合（任意・英語）:**",
        "",
        "```",
        "Dashboard refreshes on a JST schedule (1/7/13/19 JST). Same post time as our JP tweet (8pm JST ≈ US morning).",
        "```",
        "",
        "---",
        "",
        f"## {date_str}",
        "",
        "### JP — 今日の急上昇3つ",
        "",
        "```",
        jp_inner,
        "```",
        "",
        "### US — 今日の急上昇3つ（英語）",
        "",
        "```",
        us_inner,
        "```",
        "",
    ]
    return "\n".join(lines)


JST = ZoneInfo("Asia/Tokyo")
# Nominal ~20:00 JST X post. Anchor avoids using run-date when GHA schedule slips past midnight.
EVENING_X_POST_ANCHOR_HOURS = 12


def default_business_day_for_evening_x_post_jst(
    now: datetime | None = None,
) -> date:
    """JST 20時前後の X 投稿向け business_day（観測日 = 07/13/19 が揃う暦日）。

    実行時刻の暦日ではなく ``now - 12h`` の日付を使う。GitHub Actions の schedule 遅延で
    翌未明（例: 01:45 JST）に走っても、前日のスナップショットを取りに行く。
    """
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    return (now - timedelta(hours=EVENING_X_POST_ANCHOR_HOURS)).date()


def main() -> int:
    load_dotenv()

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--date",
        help=(
            "YYYY-MM-DD — business_day for snapshots "
            f"(default: JST evening-post anchor, now−{EVENING_X_POST_ANCHOR_HOURS}h calendar date)"
        ),
    )
    p.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for per-day files (default: {DEFAULT_OUTPUT_DIR})",
    )
    p.add_argument(
        "--output-file",
        default=None,
        metavar="PATH",
        help="Exact output path (overrides --output-dir; parent dirs are created)",
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
        help="Read /api/summaries/daily-snapshots (07/13/19 for --date); same rows as AI daily summary",
    )
    p.add_argument(
        "--require-slots",
        default="",
        metavar="SLOTS",
        help=(
            "Comma-separated daytime slots that must all be present (default: any one of 07/13/19). "
            "CI uses 07,13,19."
        ),
    )
    p.add_argument(
        "--wait-for-slots",
        type=int,
        default=0,
        metavar="SECONDS",
        help="With --from-api: poll until --require-slots are satisfied or timeout (0=disabled)",
    )
    p.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Seconds between snapshot API polls when --wait-for-slots > 0 (default: 60)",
    )
    p.add_argument("--dry-run", action="store_true", help="Print blocks only; do not write")
    p.add_argument("--write", action="store_true", help="Write docs/x_post_samples/daily/{date}.md")
    p.add_argument(
        "--discord",
        action="store_true",
        help=(
            "Send JP/US blocks to Discord "
            "(DISCORD_WEBHOOK_URL or --discord-webhook-url)"
        ),
    )
    p.add_argument(
        "--discord-webhook-url",
        default=None,
        metavar="URL",
        help="Override DISCORD_WEBHOOK_URL",
    )
    fr = p.add_mutually_exclusive_group()
    fr.add_argument(
        "--force-refresh",
        action="store_true",
        help="Legacy per-source HTTP only: force_refresh=true on each /api/* call (ignored with --from-api)",
    )
    fr.add_argument(
        "--no-force-refresh",
        action="store_true",
        help="Legacy per-source HTTP only: force_refresh=false (ignored with --from-api)",
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

    required_slots: tuple[str, ...] = ()
    if (args.require_slots or "").strip():
        parsed_slots = tuple(
            s.strip()
            for s in str(args.require_slots).split(",")
            if s.strip()
        )
        invalid = [s for s in parsed_slots if s not in SNAPSHOT_SLOTS_DAYTIME]
        if invalid:
            print(
                f"ERROR: invalid --require-slots {invalid!r} (allowed: {', '.join(SNAPSHOT_SLOTS_DAYTIME)})",
                file=sys.stderr,
            )
            return 1
        required_slots = parsed_slots

    d = args.date or default_business_day_for_evening_x_post_jst().isoformat()
    try:
        business_day = date.fromisoformat(d)
    except ValueError:
        print(f"ERROR: invalid --date {d!r} (expected YYYY-MM-DD)", file=sys.stderr)
        return 1

    database_url = (args.database_url or os.environ.get("DATABASE_URL") or "").strip()
    use_snapshots_db = bool(database_url) and not args.from_api
    series_by_slot = None

    if use_snapshots_db:
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
    elif args.from_api:
        base = (args.base_url or os.environ.get("TREND_DASHBOARD_BASE_URL") or BASE_DEFAULT).rstrip("/")
        print(
            f"Source: HTTP {base}/api/summaries/daily-snapshots business_day={d} "
            f"slots={'/'.join(SNAPSHOT_SLOTS_DAYTIME)}; scores=freq×{FREQ_WEIGHT}+jump×{JUMP_WEIGHT}",
            file=sys.stderr,
        )
        try:
            series_by_slot = load_snapshots_daytime_slots_from_api(
                base,
                business_day,
                required_slots=required_slots or None,
                wait_timeout_seconds=max(0, args.wait_for_slots),
                poll_interval_seconds=max(1, args.poll_interval),
            )
            jp = build_jp_block_from_snapshots(
                series_by_slot,
                d,
                inner_max=args.jp_inner_max,
                max_jp_x_weighted=args.jp_max_x_weighted,
            )
            us = build_us_block_from_snapshots(series_by_slot, d, max_chars=args.max_us_chars)
        except (
            requests.RequestException,
            TimeoutError,
            json.JSONDecodeError,
            RuntimeError,
            ValueError,
        ) as e:
            print(f"ERROR: snapshot HTTP load/compose failed: {e}", file=sys.stderr)
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
            f"Source: HTTP {base} per-source /api/* force_refresh={force_refresh}",
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
    elif args.write:
        if args.output_file:
            out_path = Path(args.output_file)
        else:
            out_path = Path(args.output_dir) / f"{d}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        body = compose_daily_markdown(d, jp, us)
        out_path.write_text(body, encoding="utf-8")
        print(f"\nWrote {out_path}", file=sys.stderr)
    elif not args.discord:
        print("\n(pass --write and/or --discord to act)", file=sys.stderr)
        return 0

    if args.discord:
        from daily_x_post_discord import notify_daily_x_post_discord, resolve_discord_webhook_url

        webhook = resolve_discord_webhook_url(args.discord_webhook_url)
        if not webhook:
            print(
                "WARN: --discord 指定ですが DISCORD_WEBHOOK_URL が未設定のためスキップ",
                file=sys.stderr,
            )
        else:
            if series_by_slot is not None:
                discord_jp, discord_us = build_x_post_blocks_for_discord_copy(
                    series_by_slot, d
                )
            else:
                discord_jp, discord_us = jp, us
            try:
                notify_daily_x_post_discord(webhook, d, discord_jp, discord_us)
            except (requests.RequestException, RuntimeError) as e:
                print(f"ERROR: Discord 通知失敗: {e}", file=sys.stderr)
                return 1
            print("Discord 通知送信完了", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
