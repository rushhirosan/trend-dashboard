#!/usr/bin/env python3
"""
直前に終了した ISO 週（月〜日）の trend_daily_snapshots を集計し、
週次サマリー Markdown を生成する（既定: 機械生成・OpenAI 不使用）。

メール本文は機械生成:
オープナー（今週カレンダー・先週マーケット・ひと息）+
先週の流れ（短文）+ いちばん動いた話題 + ホットトピック + カテゴリ top3。
来週論点は本文に含めない。Web 用リードは frontmatter の ``teaser`` / ``preview_lead``。

``--use-llm`` で従来の OpenAI 編集 JSON 生成（メール本文から編集セクションは除外）。
``--daily-only`` はレガシー（日次 md のみ・要 ``--use-llm``）。

既定入力は **スナップショット**（DB 直読 or ``--from-api``）。日次 Markdown は
補助コンテキストとして読む（欠損可）。``--daily-only`` で旧挙動（日次 md のみ）。

  python scripts/generate_ai_weekly_summary.py --from-api --dry-run
  python scripts/generate_ai_weekly_summary.py --from-api --write --force

  # LLM 編集 JSON（レガシー・メール本文からは編集セクション除外）
  export OPENAI_API_KEY=sk-...
  python scripts/generate_ai_weekly_summary.py --from-api --write --force --use-llm

詳細: ``docs/summaries/weekly/README.md``
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

JST = ZoneInfo("Asia/Tokyo")
_SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = _SCRIPT_DIR.parent
# `python scripts/foo.py` では sys.path[0] が scripts/ になる。GHA も同じ。
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import snapshot_rising as sr

DAILY_DIR = REPO_ROOT / "docs" / "summaries" / "daily"
WEEKLY_DIR = REPO_ROOT / "docs" / "summaries" / "weekly"
BASE_DEFAULT = "https://trends-dashboard.com"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_USER_CHARS = 100_000
EXPECTED_SLOTS = ("01", "07", "13", "19")
WEEKLY_RISING_PER_REGION = 1
WEEKLY_RISING_POOL_SIZE = 10
WEEKLY_CROSS_PER_REGION = 3
WEEKLY_CATEGORY_TOP_N = 3
WEEKLY_CATEGORY_POOL_LLM_MAX = 20
WEEKLY_CATEGORY_SCORE_DAY = 10
WEEKLY_CATEGORY_SCORE_CROSS = 15
# 既定は日本語ページ向け（日本ソースのみ）。US は --region us で別生成。
WEEKLY_REGIONS = ("jp",)
WEEKLY_REGION_LABELS = {"jp": "🇯🇵 日本", "us": "🇺🇸 United States"}
_ACTIVE_REGION = "jp"


def configure_weekly_region(region: str) -> None:
    """生成対象地域を切り替え（jp → weekly/、us → weekly/us/）。"""
    global WEEKLY_REGIONS, _ACTIVE_REGION
    r = (region or "jp").strip().lower()
    if r not in ("jp", "us"):
        r = "jp"
    _ACTIVE_REGION = r
    WEEKLY_REGIONS = (r,)


def weekly_output_dir() -> Path:
    return WEEKLY_DIR if _ACTIVE_REGION == "jp" else WEEKLY_DIR / "us"


def weekly_daily_assist_dir(override: Optional[Path] = None) -> Path:
    """週次の補助コンテキスト用日次ディレクトリ（同地域の日次を読む）。"""
    if override is not None:
        return override
    return DAILY_DIR if _ACTIVE_REGION == "jp" else DAILY_DIR / "us"
# 週次 rising スコア（jump 同率時の tie-break 用）
WEEKLY_SCORE_DAY = 10
WEEKLY_SCORE_SLOT = 5
WEEKLY_SCORE_JUMP = 1.0
WEEKLY_SCORE_CROSS = 25

_WEEKLY_RISING_HEADING = "## 📈 先週いちばん動いた話題"
_WEEKLY_CATEGORY_HEADING = "## 📊 カテゴリ別 — 先週の top3"
_WEEKLY_CROSS_HEADING = "## 複数ソースで週を通じて重なった話題"
_WEEKLY_HOT_HEADING = "## 🔥 週のホットトピック"
_WEEKLY_NEXT_HEADING = "## 来週に残る論点"
_WEEKLY_HOT_HEADING_US = "## 🔥 Hot topics last week"
_WEEKLY_NEXT_HEADING_US = "## What to watch next week"
# 週次「動いた」として載せる最低 jump_sum（横ばい・悪化のみは除外）
WEEKLY_RISING_MIN_JUMP = 5.0
WEEKLY_HOT_MAX = 5
WEEKLY_NEXT_MIN = 2
WEEKLY_NEXT_MAX = 3

# 週次カテゴリ top3: 同一トピック/ソースの重複を抑える
_WEEKLY_SERIES_DIVERSITY_CATEGORIES = frozenset(
    {"マーケット", "テック・開発", "検索・動画", "エンタメ・ショッピング"}
)
# 週次 digest の検索・動画: YouTube / Google Trends / Wikipedia のみ（日次カテゴリ分類とは別）
_WEEKLY_SEARCH_VIDEO_ALLOWED_PREFIXES = (
    "google_trends_",
    "youtube_trends_",
    "youtube_",
    "wikipedia_",
)
_NEWS_WEATHER_RAIN_RE = re.compile(
    r"豪雨|激しい雨|大雨|土砂崩れ|記録的短時間大雨|梅雨前線|前線活動|断続的に激しい雨"
)
_NEWS_WEATHER_RAIN_EN_RE = re.compile(
    r"\b(rain|flood|storm|hurricane|wildfire|weather alert)\b",
    re.I,
)
_NEWS_ECONOMY_RE = re.compile(r"円安|円高|株価|金融政策|日銀|金利|インフレ|景気")
_NEWS_ECONOMY_EN_RE = re.compile(
    r"\b(inflation|fed |interest rate|stock market|economy|gdp)\b",
    re.I,
)
_NEWS_SPORTS_RE = re.compile(r"対\s*\.|vs\.|試合|優勝|決勝|ワールドカップ|W杯")
_NEWS_SPORTS_EN_RE = re.compile(
    r"\bvs\.|world cup|match|championship|playoff|tournament\b",
    re.I,
)

_daily_mod: Any = None


def _daily():
    """Lazy-load generate_ai_daily_summary helpers (rising / cross / fetch)."""
    global _daily_mod
    if _daily_mod is None:
        spec = importlib.util.spec_from_file_location(
            "generate_ai_daily_summary",
            _SCRIPT_DIR / "generate_ai_daily_summary.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _daily_mod = mod
    return _daily_mod


# 週次 rising: 系列 prefix → 読者向け重要度（大きいほど compute_weekly_rising_score に加点）
_WEEKLY_SERIES_WEIGHT_15 = (
    "google_trends_",
    "youtube_trends_",
    "wikipedia_",
    "nhk_",
    "cnn_",
)
_WEEKLY_SERIES_WEIGHT_12 = (
    "hatena_",
    "worldnews_",
    "zenn_",
    "note_",
    "qiita_",
    "thehackernews_",
    "devto_",
    "hackernews_",
    "producthunt_",
)
_WEEKLY_SERIES_WEIGHT_10 = (
    "music_trends_",
    "twitch_",
    "rakuten_",
    "podcast_",
    "movie_",
    "github_",
)
_WEEKLY_SERIES_WEIGHT_3 = (
    "book_",
)
# App Store は週次「いちばん動いた」の顔にしにくいので除外
_WEEKLY_SERIES_WEIGHT_0 = (
    "appstore_",
)


def weekly_series_weight(series_key: str) -> int:
    """週次 rising 用: 系列の読者向け重要度（大きいほど優先。0 は除外）。"""
    sk = (series_key or "").strip().lower()
    if any(sk.startswith(p) for p in _WEEKLY_SERIES_WEIGHT_0):
        return 0
    if any(sk.startswith(p) for p in _WEEKLY_SERIES_WEIGHT_15):
        return 15
    if any(sk.startswith(p) for p in _WEEKLY_SERIES_WEIGHT_12):
        return 12
    if any(sk.startswith(p) for p in _WEEKLY_SERIES_WEIGHT_10):
        return 10
    if any(sk.startswith(p) for p in _WEEKLY_SERIES_WEIGHT_3):
        return 3
    return 7


def compute_weekly_rising_score(
    day_count: int,
    slot_obs: int,
    jump_sum: float,
    *,
    cross_source: bool,
    series_weight: int,
) -> float:
    return (
        day_count * WEEKLY_SCORE_DAY
        + slot_obs * WEEKLY_SCORE_SLOT
        + jump_sum * WEEKLY_SCORE_JUMP
        + (WEEKLY_SCORE_CROSS if cross_source else 0)
        + series_weight
    )


def cross_label_keys_from_daily(
    daily_cross_by_day: Dict[str, List[Dict[str, Any]]],
) -> set[str]:
    """週内の日次クロスソース候補（全件）から正規化ラベル集合を作る。"""
    keys: set[str] = set()
    for items in daily_cross_by_day.values():
        for item in items:
            label = str(item.get("label") or "").strip()
            if label:
                keys.add(sr.normalize_label_key(label))
    return keys


def iso_week_stem(d: date) -> str:
    iso_y, iso_w, _ = d.isocalendar()
    return f"{iso_y}-W{iso_w:02d}"


def week_range_mon_sun(any_day_in_week: date) -> Tuple[date, date]:
    mon = any_day_in_week - timedelta(days=any_day_in_week.isoweekday() - 1)
    sun = mon + timedelta(days=6)
    return mon, sun


def week_dates(mon: date) -> List[date]:
    return [mon + timedelta(days=i) for i in range(7)]


def default_week_mon_jst(now: Optional[datetime] = None) -> date:
    """直前に終了した ISO 週の月曜（JST カレンダー）。"""
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    today = now.date()
    this_mon = today - timedelta(days=today.isoweekday() - 1)
    return this_mon - timedelta(days=7)


def use_http_snapshots(*, cli_from_api: bool, database_url: str) -> bool:
    if cli_from_api:
        return True
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return False
    if not database_url:
        return True
    lo = database_url.lower()
    return ".flycast" in lo or ".internal" in lo


def split_front_matter(raw: str) -> Tuple[str, str]:
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_daily_markdown(daily_path: Path) -> Optional[str]:
    if not daily_path.is_file():
        return None
    raw = daily_path.read_text(encoding="utf-8")
    _, body = split_front_matter(raw)
    return body.strip() or None


def build_daily_rollups(
    mon: date, sun: date, daily_dir: Path
) -> Tuple[str, Dict[str, Any]]:
    """日次 Markdown 補助テキストとメタ。"""
    meta: Dict[str, Any] = {
        "week_mon": mon.isoformat(),
        "week_sun": sun.isoformat(),
        "iso_week": iso_week_stem(mon),
        "daily_files": [],
        "missing_dates": [],
    }
    chunks: List[str] = []
    for d in week_dates(mon):
        rel = f"docs/summaries/daily/{d.isoformat()}.md"
        p = daily_dir / f"{d.isoformat()}.md"
        body = load_daily_markdown(p)
        entry = {"date": d.isoformat(), "path": rel, "found": body is not None}
        meta["daily_files"].append(entry)
        if body is None:
            meta["missing_dates"].append(d.isoformat())
            chunks.append(
                f"## 日次サマリー — {d.isoformat()}（JST）\n\n（ファイルなし: {rel}）\n"
            )
        else:
            chunks.append(f"## 日次サマリー — {d.isoformat()}（JST）\n\n{body}\n")

    text = "\n".join(chunks).strip()
    if len(text) > MAX_USER_CHARS:
        text = text[:MAX_USER_CHARS] + "\n…(truncated)"
        meta["truncated"] = True
    else:
        meta["truncated"] = False
    return text, meta


def _snapshot_day_status(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    slots: Dict[str, int] = defaultdict(int)
    for row in rows:
        slots[str(row.get("slot") or "")] += 1
    missing_slots = [s for s in EXPECTED_SLOTS if slots.get(s, 0) == 0]
    return {
        "row_count": len(rows),
        "slots": dict(slots),
        "missing_slots": missing_slots,
        "found": len(rows) > 0,
        "complete": len(rows) > 0 and not missing_slots,
    }


def fetch_day_snapshots(
    business_day: date,
    *,
    via_http: bool,
    database_url: str,
    base_url: str,
    connect_timeout: int,
    request_timeout: int,
) -> List[Dict[str, Any]]:
    daily = _daily()
    if via_http:
        return daily.fetch_snapshots_from_api(base_url, business_day, timeout=request_timeout)
    return daily.fetch_snapshots(database_url, business_day, connect_timeout=connect_timeout)


def build_week_snapshot_rollups(
    mon: date,
    *,
    via_http: bool,
    database_url: str,
    base_url: str,
    connect_timeout: int,
    request_timeout: int,
) -> Tuple[
    Dict[str, Any],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
]:
    """7日分スナップショットを読み、地域別の週次急上昇・カテゴリ digest・クロスソース集計とメタを返す。"""
    meta: Dict[str, Any] = {
        "iso_week": iso_week_stem(mon),
        "week_mon": mon.isoformat(),
        "week_sun": (mon + timedelta(days=6)).isoformat(),
        "snapshot_days": [],
        "missing_snapshot_dates": [],
        "partial_snapshot_dates": [],
        "input_mode": "snapshots",
    }
    daily = _daily()
    daily_rising_by_region_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        r: {} for r in WEEKLY_REGIONS
    }
    daily_cross_by_region_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        r: {} for r in WEEKLY_REGIONS
    }
    daily_category_by_region_day: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        r: {} for r in WEEKLY_REGIONS
    }

    for d in week_dates(mon):
        ds = d.isoformat()
        try:
            rows = fetch_day_snapshots(
                d,
                via_http=via_http,
                database_url=database_url,
                base_url=base_url,
                connect_timeout=connect_timeout,
                request_timeout=request_timeout,
            )
        except Exception as exc:
            rows = []
            meta.setdefault("fetch_errors", {})[ds] = str(exc)

        st = _snapshot_day_status(rows)
        entry = {"date": ds, **st}
        meta["snapshot_days"].append(entry)
        if not st["found"]:
            meta["missing_snapshot_dates"].append(ds)
            continue
        if not st["complete"]:
            meta["partial_snapshot_dates"].append(ds)

        for region in WEEKLY_REGIONS:
            region_rows = daily.filter_rows_by_region(rows, region)
            if not region_rows:
                continue
            daily_rising_by_region_day[region][ds] = daily.build_rising_highlights(
                region_rows, count=None
            )
            daily_cross_by_region_day[region][ds] = daily.build_cross_source_highlights(
                region_rows, count=None
            )
            daily_category_by_region_day[region][ds] = daily.build_category_top3(
                region_rows, count=daily.CATEGORY_TOP_N
            )

    weekly_rising_pools: Dict[str, List[Dict[str, Any]]] = {}
    weekly_rising: Dict[str, List[Dict[str, Any]]] = {}
    weekly_cross: Dict[str, List[Dict[str, Any]]] = {}
    weekly_category: Dict[str, List[Dict[str, Any]]] = {}
    for region in WEEKLY_REGIONS:
        cross_keys = cross_label_keys_from_daily(daily_cross_by_region_day[region])
        weekly_rising_pools[region] = aggregate_weekly_rising(
            daily_rising_by_region_day[region],
            count=WEEKLY_RISING_POOL_SIZE,
            cross_label_keys=cross_keys,
        )
    weekly_rising = pick_regional_weekly_rising(weekly_rising_pools)
    for region in WEEKLY_REGIONS:
        cross_keys = cross_label_keys_from_daily(daily_cross_by_region_day[region])
        weekly_cross[region] = aggregate_weekly_cross_source(
            daily_cross_by_region_day[region],
            count=WEEKLY_CROSS_PER_REGION,
        )
        weekly_category[region] = aggregate_weekly_category_top3(
            daily_category_by_region_day[region],
            cross_label_keys=cross_keys,
        )
        for item in weekly_rising.get(region) or []:
            item["region"] = region
        for item in weekly_cross[region]:
            item["region"] = region

    meta["snapshot_days_found"] = sum(1 for x in meta["snapshot_days"] if x.get("found"))
    meta["weekly_rising_counts"] = {r: len(weekly_rising[r]) for r in WEEKLY_REGIONS}
    meta["weekly_cross_counts"] = {r: len(weekly_cross[r]) for r in WEEKLY_REGIONS}
    meta["weekly_category_counts"] = {
        r: sum(len(b.get("items") or []) for b in weekly_category[r])
        for r in WEEKLY_REGIONS
    }
    return meta, weekly_rising, weekly_cross, weekly_category


def aggregate_weekly_rising(
    daily_rising_by_day: Dict[str, List[Dict[str, Any]]],
    *,
    count: int = WEEKLY_RISING_PER_REGION,
    cross_label_keys: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    """日次 rising 候補（資格あり全件）をラベルで週次集約し、週次スコアで順位付け。"""
    cross_keys = cross_label_keys or set()
    by_label: Dict[str, Dict[str, Any]] = {}

    for ds, items in daily_rising_by_day.items():
        for item in items:
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            nk = sr.normalize_label_key(label)
            sk = str(item.get("series_key") or "")
            sw = weekly_series_weight(sk)
            if sw <= 0:
                continue
            agg = by_label.get(nk)
            if agg is None:
                agg = {
                    "label": label,
                    "days": set(),
                    "jump_sum": 0.0,
                    "slot_obs": 0,
                    "best_rank": 999,
                    "series_weight": sw,
                    "series_key": sk,
                    "category": item.get("category") or "",
                    "url": item.get("url"),
                    "link_line": item.get("link_line"),
                    "rank_evidence_by_day": {},
                }
                by_label[nk] = agg
            agg["days"].add(ds)
            agg["jump_sum"] += float(item.get("jump") or 0)
            agg["slot_obs"] += int(item.get("freq_slots") or 0)
            ranks = item.get("ranks") or {}
            if ranks:
                day_best = min(int(v) for v in ranks.values())
                agg["best_rank"] = min(agg["best_rank"], day_best)
            elif item.get("r_best") is not None:
                agg["best_rank"] = min(agg["best_rank"], int(item["r_best"]))
            if sw > agg["series_weight"]:
                agg["series_weight"] = sw
                agg["series_key"] = sk
                if item.get("url"):
                    agg["url"] = item["url"]
                if item.get("link_line"):
                    agg["link_line"] = item["link_line"]
            elif not agg.get("link_line") and item.get("link_line"):
                agg["link_line"] = item["link_line"]
            if item.get("url") and not agg.get("url"):
                agg["url"] = item["url"]
            if item.get("rank_evidence"):
                agg["rank_evidence_by_day"][ds] = item["rank_evidence"]
            if item.get("category"):
                agg["category"] = item["category"]

    pool: List[Dict[str, Any]] = []
    for raw in by_label.values():
        day_count = len(raw["days"])
        cross = sr.normalize_label_key(raw["label"]) in cross_keys
        score = compute_weekly_rising_score(
            day_count,
            int(raw["slot_obs"]),
            float(raw["jump_sum"]),
            cross_source=cross,
            series_weight=int(raw["series_weight"]),
        )
        pool.append({**raw, "day_count": day_count, "cross_source": cross, "weekly_score": score})

    pool.sort(
        key=lambda x: (
            -x["weekly_score"],
            -x["day_count"],
            -x["jump_sum"],
            x["best_rank"],
            x["label"],
        )
    )
    out: List[Dict[str, Any]] = []
    for raw in pool[:count]:
        days_sorted = sorted(raw["days"])
        out.append(
            {
                "label": raw["label"],
                "days": days_sorted,
                "day_count": raw["day_count"],
                "jump_sum": round(raw["jump_sum"], 1),
                "slot_obs": raw["slot_obs"],
                "weekly_score": round(raw["weekly_score"], 1),
                "cross_source": raw["cross_source"],
                "best_rank": raw["best_rank"] if raw["best_rank"] < 999 else None,
                "category": raw["category"],
                "series_key": raw.get("series_key") or "",
                "url": raw.get("url"),
                "link_line": raw.get("link_line"),
                "rank_evidence_by_day": raw.get("rank_evidence_by_day") or {},
            }
        )
    return out


def aggregate_weekly_cross_source(
    daily_cross_by_day: Dict[str, List[Dict[str, Any]]],
    *,
    count: int = WEEKLY_CROSS_PER_REGION,
) -> List[Dict[str, Any]]:
    """日次クロスソース候補をラベルで週次集約。"""
    by_label: Dict[str, Dict[str, Any]] = {}

    for ds, items in daily_cross_by_day.items():
        for item in items:
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            nk = sr.normalize_label_key(label)
            agg = by_label.get(nk)
            if agg is None:
                agg = {
                    "label": label,
                    "days": set(),
                    "providers": set(),
                    "sources_display": item.get("sources_display") or "",
                    "rank_evidence_by_day": {},
                    "best_daytime_rank": 999,
                    "max_jump": 0.0,
                }
                by_label[nk] = agg
            agg["days"].add(ds)
            agg["providers"].update(item.get("providers") or [])
            if item.get("sources_display"):
                agg["sources_display"] = item["sources_display"]
            if item.get("rank_evidence"):
                agg["rank_evidence_by_day"][ds] = item["rank_evidence"]
            br = item.get("best_daytime_rank")
            if br is not None:
                agg["best_daytime_rank"] = min(agg["best_daytime_rank"], int(br))
            agg["max_jump"] = max(agg["max_jump"], float(item.get("jump") or 0))

    pool = list(by_label.values())
    pool.sort(
        key=lambda x: (
            -len(x["days"]),
            -len(x["providers"]),
            x.get("best_daytime_rank") or 999,
            -x["max_jump"],
            x["label"],
        )
    )
    out: List[Dict[str, Any]] = []
    for raw in pool[:count]:
        days_sorted = sorted(raw["days"])
        out.append(
            {
                "label": raw["label"],
                "days": days_sorted,
                "day_count": len(days_sorted),
                "providers": sorted(raw["providers"]),
                "sources_display": raw.get("sources_display") or "",
                "rank_evidence_by_day": raw.get("rank_evidence_by_day") or {},
                "best_daytime_rank": raw.get("best_daytime_rank"),
                "max_jump": round(raw.get("max_jump") or 0, 1),
            }
        )
    return out


def weekly_rising_is_significant(item: Dict[str, Any]) -> bool:
    """週内で実質的に順位が改善した話題か（横ばい・悪化のみは除外）。"""
    return float(item.get("jump_sum") or 0) >= WEEKLY_RISING_MIN_JUMP


def pick_regional_weekly_rising(
    pools: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """地域別 rising top1。有意な jump のみ。日本で選んだラベルと同一の話題は米国でスキップ。"""
    used_nks: set[str] = set()
    out: Dict[str, List[Dict[str, Any]]] = {}
    for region in WEEKLY_REGIONS:
        picked: Optional[Dict[str, Any]] = None
        for item in pools.get(region) or []:
            if not weekly_rising_is_significant(item):
                continue
            nk = sr.normalize_label_key(str(item.get("label") or ""))
            if region != "jp" and nk in used_nks:
                continue
            picked = item
            used_nks.add(nk)
            break
        out[region] = [picked] if picked else []
    return out


def _weekly_category_sort_key(item: Dict[str, Any]) -> tuple:
    return (
        -int(item.get("weekly_score") or 0),
        -int(item.get("day_count") or 0),
        item.get("best_rank") or 999,
        str(item.get("label") or ""),
    )


def _news_diversity_bucket(label: str) -> str:
    """ニュース: 同じ出来事の別見出しを1バケットにまとめる。"""
    if _NEWS_WEATHER_RAIN_RE.search(label) or _NEWS_WEATHER_RAIN_EN_RE.search(label):
        return "news:weather"
    if _NEWS_ECONOMY_RE.search(label) or _NEWS_ECONOMY_EN_RE.search(label):
        return "news:economy"
    if _NEWS_SPORTS_RE.search(label) or _NEWS_SPORTS_EN_RE.search(label):
        return "news:sports"
    return f"news:{sr.normalize_label_key(label)[:120]}"


def weekly_category_diversity_bucket(category: str, item: Dict[str, Any]) -> str:
    """週次 top3 選定用: カテゴリ内の重複抑制バケット。"""
    label = str(item.get("label") or "")
    sk = str(item.get("series_key") or "").strip().lower()
    if category == "ニュース":
        return _news_diversity_bucket(label)
    if category in _WEEKLY_SERIES_DIVERSITY_CATEGORIES:
        return f"series:{sk}" if sk else f"label:{sr.normalize_label_key(label)}"
    return f"label:{sr.normalize_label_key(label)}"


def _bucket_merges_rank_days(category: str, bucket: str) -> bool:
    return category == "ニュース" and bucket == "news:weather"


def _weekly_item_belongs_to_category(category: str, item: Dict[str, Any]) -> bool:
    """週次 digest: 日次カテゴリ分類と一致する series のみ許可（検索・動画は週次サブセット）。"""
    sk = str(item.get("series_key") or "").strip()
    if not sk:
        return False
    daily = _daily()
    if daily.categorize_series_key(sk) != category:
        return False
    if category == "検索・動画":
        sk_l = sk.lower()
        return any(sk_l.startswith(p) for p in _WEEKLY_SEARCH_VIDEO_ALLOWED_PREFIXES)
    return True


def _filter_weekly_category_pool(
    pool: List[Dict[str, Any]], category: str
) -> List[Dict[str, Any]]:
    """カテゴリ外 series を週次プールから除外。"""
    return [item for item in pool if _weekly_item_belongs_to_category(category, item)]


def _pick_fill_diverse_by_series(
    pool: List[Dict[str, Any]],
    count: int,
    *,
    category: str,
) -> List[Dict[str, Any]]:
    """Pass1: 各 series から1件。Pass2: スコア順で不足分を埋める（同一 series 可）。"""
    sorted_pool = sorted(pool, key=_weekly_category_sort_key)
    picked: List[Dict[str, Any]] = []
    picked_nks: set[str] = set()
    series_seen: set[str] = set()

    for item in sorted_pool:
        if len(picked) >= count:
            break
        sk = str(item.get("series_key") or "").strip().lower()
        series_key = sk or sr.normalize_label_key(str(item.get("label") or ""))
        if series_key in series_seen:
            continue
        series_seen.add(series_key)
        picked.append(item)
        picked_nks.add(sr.normalize_label_key(str(item.get("label") or "")))

    if len(picked) >= count:
        return picked

    for item in sorted_pool:
        if len(picked) >= count:
            break
        nk = sr.normalize_label_key(str(item.get("label") or ""))
        if nk in picked_nks:
            continue
        picked.append(item)
        picked_nks.add(nk)

    return picked


def pick_diverse_weekly_category_items(
    pool: List[Dict[str, Any]],
    category: str,
    count: int,
) -> List[Dict[str, Any]]:
    """スコア順プールから、トピック/ソース重複を抑えて最大 count 件を選ぶ。"""
    pool = _filter_weekly_category_pool(pool, category)
    if not pool:
        return []

    if category == "ニュース":
        by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in pool:
            by_bucket[weekly_category_diversity_bucket(category, item)].append(item)

        representatives: List[Dict[str, Any]] = []
        for bucket, items in by_bucket.items():
            items_sorted = sorted(items, key=_weekly_category_sort_key)
            rep = dict(items_sorted[0])
            if _bucket_merges_rank_days(category, bucket) and len(items) > 1:
                rep["rank_display_by_day"] = merge_theme_rank_by_day(items)
                rep["day_count"] = len(rep.get("rank_display_by_day") or {})
                rep["days"] = sorted((rep.get("rank_display_by_day") or {}).keys())
            representatives.append(rep)

        representatives.sort(key=_weekly_category_sort_key)
        return representatives[:count]

    if category in _WEEKLY_SERIES_DIVERSITY_CATEGORIES:
        return _pick_fill_diverse_by_series(pool, count, category=category)

    sorted_pool = sorted(pool, key=_weekly_category_sort_key)
    return sorted_pool[:count]


def _weekly_category_item_payload(item: Dict[str, Any], cat: str) -> Dict[str, Any]:
    return {
        "label": item["label"],
        "category": cat,
        "day_count": item["day_count"],
        "days": item["days"],
        "best_rank": item["best_rank"],
        "cross_source": item["cross_source"],
        "url": item.get("url"),
        "link_line": item.get("link_line"),
        "series_key": item.get("series_key"),
        "peak_day": item.get("peak_day"),
        "peak_rank_display": item.get("peak_rank_display") or "",
        "rank_display_by_day": item.get("rank_display_by_day") or {},
    }


def aggregate_weekly_category_top3(
    daily_category_by_day: Dict[str, List[Dict[str, Any]]],
    *,
    count: int = WEEKLY_CATEGORY_TOP_N,
    cross_label_keys: Optional[set[str]] = None,
) -> List[Dict[str, Any]]:
    """日次カテゴリ top3 をラベル×カテゴリで週次集約（出現日数・最高順位・系列重み）。"""
    daily = _daily()
    cross_keys = cross_label_keys or set()
    by_category: Dict[str, Dict[str, Dict[str, Any]]] = {
        cat: {} for cat in daily.CATEGORY_DIGEST_ORDER
    }

    for ds, blocks in daily_category_by_day.items():
        for block in blocks:
            cat = str(block.get("category") or "")
            if cat not in by_category:
                continue
            for item in block.get("items") or []:
                label = str(item.get("label") or "").strip()
                if not label:
                    continue
                nk = sr.normalize_label_key(label)
                sk = str(item.get("series_key") or "")
                sw = weekly_series_weight(sk)
                day_best = _best_rank_from_evidence(str(item.get("rank_display") or ""))

                agg = by_category[cat].get(nk)
                if agg is None:
                    agg = {
                        "label": label,
                        "category": cat,
                        "days": set(),
                        "best_rank": 999,
                        "series_weight": sw,
                        "series_key": sk,
                        "url": item.get("url"),
                        "link_line": item.get("link_line"),
                        "rank_display_by_day": {},
                        "peak_day": None,
                        "peak_rank_display": "",
                    }
                    by_category[cat][nk] = agg
                rank_disp = str(item.get("rank_display") or "")
                agg["rank_display_by_day"][ds] = rank_disp
                agg["days"].add(ds)
                if day_best is not None:
                    if day_best < agg["best_rank"]:
                        agg["best_rank"] = day_best
                        agg["peak_day"] = ds
                        agg["peak_rank_display"] = rank_disp
                    elif day_best == agg["best_rank"] and not agg.get("peak_day"):
                        agg["peak_day"] = ds
                        agg["peak_rank_display"] = rank_disp
                if sw > agg["series_weight"]:
                    agg["series_weight"] = sw
                    agg["series_key"] = sk
                    if item.get("url"):
                        agg["url"] = item["url"]
                    if item.get("link_line"):
                        agg["link_line"] = item["link_line"]
                elif not agg.get("link_line") and item.get("link_line"):
                    agg["link_line"] = item["link_line"]

    out_blocks: List[Dict[str, Any]] = []
    for cat in daily.CATEGORY_DIGEST_ORDER:
        pool: List[Dict[str, Any]] = []
        for raw in by_category[cat].values():
            day_count = len(raw["days"])
            cross = sr.normalize_label_key(raw["label"]) in cross_keys
            score = (
                day_count * WEEKLY_CATEGORY_SCORE_DAY
                + (WEEKLY_CATEGORY_SCORE_CROSS if cross else 0)
                + int(raw["series_weight"])
            )
            best = raw["best_rank"] if raw["best_rank"] < 999 else None
            pool.append(
                {
                    **raw,
                    "day_count": day_count,
                    "days": sorted(raw["days"]),
                    "cross_source": cross,
                    "weekly_score": score,
                    "best_rank": best,
                }
            )
        pool.sort(key=_weekly_category_sort_key)
        picked_raw = pick_diverse_weekly_category_items(pool, cat, count)
        picked = [_weekly_category_item_payload(item, cat) for item in picked_raw]
        pool_filtered = _filter_weekly_category_pool(pool, cat)
        pool_all = [_weekly_category_item_payload(item, cat) for item in pool_filtered]
        out_blocks.append(
            {
                "category": cat,
                "items": picked,
                "pool": pool_all,
                "quiet": len(picked) == 0,
            }
        )
    return out_blocks


def _category_candidate_for_llm(item: Dict[str, Any]) -> Dict[str, Any]:
    """LLM テーマ統合用の候補（ラベル・日数・順位のみ）。"""
    return {
        "label": item.get("label"),
        "day_count": item.get("day_count"),
        "days": item.get("days"),
        "best_rank": item.get("best_rank"),
        "cross_source": bool(item.get("cross_source")),
    }


def build_mechanical_llm_payload(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_cross: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """LLM 向けに地域別の週次機械集計を JSON 化。"""
    regions: Dict[str, Any] = {}
    for region in WEEKLY_REGIONS:
        pool_blocks: List[Dict[str, Any]] = []
        for block in weekly_category.get(region) or []:
            candidates = block.get("pool") or block.get("items") or []
            pool_blocks.append(
                {
                    "category": block.get("category"),
                    "candidates": [
                        _category_candidate_for_llm(c)
                        for c in candidates[:WEEKLY_CATEGORY_POOL_LLM_MAX]
                    ],
                }
            )
        regions[region] = {
            "weekly_category_pool": pool_blocks,
            "weekly_category_digest": weekly_category.get(region) or [],
            "weekly_rising": weekly_rising.get(region) or [],
            "weekly_cross_source": weekly_cross.get(region) or [],
        }
    return {"regions": regions}


_RANK_EVIDENCE_SLOT_RE = re.compile(r"(\d+)時(?:(\d+)位|圏外)")
_DAYTIME_SLOT_KEYS = ("07", "13", "19")


def _short_calendar_date(ds: str) -> str:
    """2026-06-08 → 06-08"""
    try:
        return date.fromisoformat(ds).strftime("%m-%d")
    except ValueError:
        return ds


def parse_rank_evidence(evidence: str) -> Dict[str, Optional[int]]:
    """rank_evidence 文字列を {07,13,19} → 順位（圏外は None）に分解。"""
    ranks: Dict[str, Optional[int]] = {s: None for s in _DAYTIME_SLOT_KEYS}
    for m in _RANK_EVIDENCE_SLOT_RE.finditer(evidence or ""):
        slot = m.group(1).zfill(2)
        if slot not in ranks:
            continue
        rank_str = m.group(2)
        ranks[slot] = int(rank_str) if rank_str else None
    return ranks


def _format_rank_cell(rank: Optional[int]) -> str:
    return "—" if rank is None else str(rank)


def _day_count_for_item(item: Dict[str, Any]) -> int:
    day_count = item.get("day_count")
    if day_count is None and item.get("days"):
        return len(item["days"])
    return int(day_count or 0)


def _compact_rank_display(rank_display: str) -> str:
    """スロット横断の順位表記を短くする（全スロット同順位なら N位 のみ）。"""
    ranks = parse_rank_evidence(rank_display)
    vals = [r for r in ranks.values() if r is not None]
    if not vals:
        return (rank_display or "").strip() or "圏外"
    if len(set(vals)) == 1:
        return f"{vals[0]}位"
    return (rank_display or "").strip()


def _format_rank_chain(rank_by_day: Dict[str, str]) -> str:
    """日別ベスト順位を矢印なしの連鎖にする。"""
    points: List[tuple[str, int]] = []
    for ds, ev in sorted(rank_by_day.items()):
        best = _best_rank_from_evidence(ev)
        if best is not None:
            points.append((ds, best))
    if not points:
        return ""
    if len(points) == 1:
        ds, r = points[0]
        return f"{_short_calendar_date(ds)} {r}位"
    return " → ".join(f"{_short_calendar_date(ds)} ({r}位)" for ds, r in points)


def merge_theme_rank_by_day(items: List[Dict[str, Any]]) -> Dict[str, str]:
    """テーマ内複数ラベルの日別 rank_display をマージ（同日はベスト順位を採用）。"""
    merged: Dict[str, str] = {}
    for item in items:
        for ds, ev in (item.get("rank_display_by_day") or {}).items():
            if ds not in merged:
                merged[ds] = ev
                continue
            old_best = _best_rank_from_evidence(merged[ds])
            new_best = _best_rank_from_evidence(ev)
            if new_best is not None and (old_best is None or new_best < old_best):
                merged[ds] = ev
    return merged


def format_theme_evidence_line(items: List[Dict[str, Any]]) -> str:
    """テーマ1件分の根拠行（日別ベスト順位の連鎖）。"""
    merged = merge_theme_rank_by_day(items)
    if not merged:
        return ""
    chain = _format_rank_chain(merged)
    if not chain:
        return ""
    parts: List[str] = [chain]
    if any(item.get("cross_source") for item in items):
        parts.append("複数ソース")
    return "> " + " · ".join(parts)


def build_category_label_index(
    blocks: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """category → normalize_label_key → 候補 item。"""
    index: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for block in blocks:
        cat = str(block.get("category") or "")
        if not cat:
            continue
        bucket = index.setdefault(cat, {})
        for item in (block.get("pool") or []) + (block.get("items") or []):
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            nk = sr.normalize_label_key(label)
            if nk not in bucket:
                bucket[nk] = item
    return index


def _pick_primary_theme_item(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """テーマ表示用: 最高順位・出現日数で代表候補を選ぶ。"""
    if not items:
        return None
    return min(
        items,
        key=lambda x: (
            x.get("best_rank") or 999,
            -(x.get("day_count") or 0),
            str(x.get("label") or ""),
        ),
    )


def format_theme_display_line(theme: Dict[str, Any]) -> str:
    """カテゴリ digest 1件: ソース由来の具体ラベルでリンク表示（抽象タイトルは使わない）。"""
    items = theme.get("items") or []
    primary = _pick_primary_theme_item(items)
    if primary is None:
        return ""
    link_line = _compact_weekly_link_line(primary)
    return link_line or str(primary.get("label") or "")


def resolve_region_category_themes(
    region: str,
    editorial: Dict[str, Any],
    weekly_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """機械週次 top3 をそのまま表示（具体ラベル・リンクを維持。LLM テーマは使わない）。"""
    daily = _daily()
    blocks_by_cat = {str(b.get("category") or ""): b for b in weekly_blocks}

    out: List[Dict[str, Any]] = []
    for cat in daily.CATEGORY_DIGEST_ORDER:
        block = blocks_by_cat.get(cat) or {}
        mechanical_items = block.get("items") or []
        rendered: List[Dict[str, Any]] = []
        for it in mechanical_items[:WEEKLY_CATEGORY_TOP_N]:
            label = str(it.get("label") or "").strip()
            if not label:
                continue
            rendered.append({"items": [it]})
        if rendered:
            out.append({"category": cat, "themes": rendered})
    return out


def _parse_category_themes_region(
    data: Dict[str, Any],
    key: str,
) -> Dict[str, List[Dict[str, Any]]]:
    daily = _daily()
    valid_cats = set(daily.CATEGORY_DIGEST_ORDER)
    raw = data.get(key)
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not isinstance(raw, list):
        return out
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cat = str(entry.get("category") or "").strip()
        if cat not in valid_cats:
            continue
        themes_raw = entry.get("themes")
        if not isinstance(themes_raw, list):
            continue
        themes: List[Dict[str, Any]] = []
        for t in themes_raw[:WEEKLY_CATEGORY_TOP_N]:
            if not isinstance(t, dict):
                continue
            title = str(t.get("title") or "").strip()
            if not title:
                continue
            labels_raw = t.get("labels")
            if not isinstance(labels_raw, list):
                labels_raw = [t.get("label")] if t.get("label") else []
            labels = [str(x).strip() for x in labels_raw if str(x).strip()]
            if not labels:
                continue
            themes.append(
                {
                    "title": title,
                    "blurb": str(t.get("blurb") or "").strip(),
                    "labels": labels,
                }
            )
        if themes:
            out[cat] = themes
    return out


def render_weekly_category_markdown(
    weekly_category: Dict[str, List[Dict[str, Any]]],
    editorial: Dict[str, Any],
) -> str:
    empty_msg = (
        "(No notable category topics last week.)"
        if _ACTIVE_REGION == "us"
        else "（先週、カテゴリ別の注目話題は見つかりませんでした）"
    )
    heading = (
        "## 📊 Category top3 last week"
        if _ACTIVE_REGION == "us"
        else _WEEKLY_CATEGORY_HEADING
    )
    lines: List[str] = [heading, ""]
    any_items = False
    single_region = len(WEEKLY_REGIONS) == 1
    for region in WEEKLY_REGIONS:
        blocks = weekly_category.get(region) or []
        theme_blocks = resolve_region_category_themes(region, editorial, blocks)
        if not single_region:
            lines.append(f"### {WEEKLY_REGION_LABELS[region]}")
            lines.append("")
        if not theme_blocks:
            lines.append(empty_msg)
            lines.append("")
            continue
        any_items = True
        for block in theme_blocks:
            cat = str(block.get("category") or "")
            themes = block.get("themes") or []
            lines.append(f"#### {cat}")
            lines.append("")
            for i, theme in enumerate(themes, 1):
                lines.append(f"{i}. {format_theme_display_line(theme)}")
                evidence = format_theme_evidence_line(theme.get("items") or [])
                if evidence:
                    lines.append(evidence)
                lines.append("")
    if not any_items:
        return f"{heading}\n\n{empty_msg}\n"
    return "\n".join(lines).rstrip() + "\n"


def format_weekly_rising_movement_block(item: Dict[str, Any]) -> str:
    """急上昇向け: 週内の日別ベスト順位（矢印・注釈なし）。"""
    rank_by_day = item.get("rank_evidence_by_day") or {}
    chain = _format_rank_chain(rank_by_day)
    if not chain:
        return ""
    return f"> **週内の動き**: {chain}\n"


def format_weekly_rank_table(rank_evidence_by_day: Dict[str, str]) -> str:
    """07/13/19 の順位を日付×スロットの Markdown 表にする。"""
    if not rank_evidence_by_day:
        return ""
    header = "| 日 | 07 | 13 | 19 |"
    sep = "|:--:|:-:|:-:|:-:|"
    rows: List[str] = [header, sep]
    for ds, ev in sorted(rank_evidence_by_day.items()):
        ranks = parse_rank_evidence(ev)
        rows.append(
            "| "
            + " | ".join(
                [
                    _short_calendar_date(ds),
                    _format_rank_cell(ranks["07"]),
                    _format_rank_cell(ranks["13"]),
                    _format_rank_cell(ranks["19"]),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _best_rank_from_evidence(evidence: str) -> Optional[int]:
    vals = [r for r in parse_rank_evidence(evidence).values() if r is not None]
    return min(vals) if vals else None



def _weekly_rank_chart_series(
    rank_evidence_by_day: Dict[str, str],
) -> Optional[Tuple[List[str], List[str], List[int]]]:
    points: List[tuple[str, int]] = []
    for ds, ev in sorted(rank_evidence_by_day.items()):
        best = _best_rank_from_evidence(ev)
        if best is not None:
            points.append((_short_calendar_date(ds), best))
    if len(points) < 2:
        return None
    rank_vals = [r for _, r in points]
    if len(set(rank_vals)) < 2:
        return None
    date_labels = [d for d, _ in points]
    x_labels = [f"{d} ({r}位)" for d, r in points]
    return x_labels, date_labels, rank_vals


def format_weekly_rank_trend_block(
    label: str,
    rank_evidence_by_day: Dict[str, str],
) -> str:
    """週内ベスト順位のテキスト一行（Markdown / メール共通。画像なし）。"""
    series = _weekly_rank_chart_series(rank_evidence_by_day)
    if not series:
        return ""
    x_labels, _, rank_vals = series
    trend = sr.format_rank_trend_markdown(x_labels, rank_vals)
    if not trend:
        return ""
    return trend.replace("**順位の動き**", "**日別ベスト順位**", 1) + "\n"


def format_weekly_best_rank_block(
    label: str,
    rank_evidence_by_day: Dict[str, str],
    **_: Any,
) -> str:
    """後方互換エイリアス（``format_weekly_rank_trend_block``）。"""
    return format_weekly_rank_trend_block(label, rank_evidence_by_day)


def _compact_weekly_link_line(item: Dict[str, Any]) -> str:
    """週次表示用: link_line から順位表記を除き、ソース名だけ残す。"""
    link = str(item.get("link_line") or "").strip()
    if not link:
        return str(item.get("label") or "")
    m = re.match(r"^(\[[^\]]+\]\([^)]+\))（([^·）]+)", link)
    if m:
        return f"{m.group(1)}（{m.group(2).strip()}）"
    return re.sub(r"（[^）]*）\s*$", "", link)


_MD_LINK_TITLE_RE = re.compile(r"^\[([^\]]+)\]\([^)]+\)\s*")


def _strip_md_link_title(title: str) -> str:
    """見出しが既に Markdown リンクならラベルだけ取り出す。"""
    s = (title or "").strip()
    m = _MD_LINK_TITLE_RE.match(s)
    if m:
        rest = s[m.end() :].strip()
        # 末尾の（ソース）はマッチ用に落とす
        rest = re.sub(r"^（[^）]*）\s*", "", rest)
        return m.group(1).strip() or s
    return s


def _iter_weekly_link_source_items(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """ホットトピック照合用: rising + カテゴリ pool/items を集める。"""
    items: List[Dict[str, Any]] = []
    for region in WEEKLY_REGIONS:
        for it in weekly_rising.get(region) or []:
            if isinstance(it, dict):
                items.append(it)
        for block in weekly_category.get(region) or []:
            if not isinstance(block, dict):
                continue
            for key in ("pool", "items"):
                for it in block.get(key) or []:
                    if isinstance(it, dict):
                        items.append(it)
    return items


def build_hot_topic_link_index(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """label（大小無視）→ 機械側アイテム。URL / link_line 付きを優先。"""
    index: Dict[str, Dict[str, Any]] = {}
    for it in _iter_weekly_link_source_items(weekly_rising, weekly_category):
        label = str(it.get("label") or "").strip()
        if not label:
            continue
        key = label.casefold()
        has_link = bool(str(it.get("link_line") or "").strip() or str(it.get("url") or "").strip())
        prev = index.get(key)
        if prev is None:
            index[key] = it
            continue
        prev_has = bool(
            str(prev.get("link_line") or "").strip() or str(prev.get("url") or "").strip()
        )
        if has_link and not prev_has:
            index[key] = it
    return index


def _hot_topic_heading_line(title: str, matched: Optional[Dict[str, Any]]) -> str:
    """ホット見出し: 機械リンクがあれば [title](url)（ソース）、なければプレーン。"""
    plain = _strip_md_link_title(title)
    if not matched:
        return plain
    link = _compact_weekly_link_line(matched)
    if not link or link == str(matched.get("label") or ""):
        url = str(matched.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            return f"[{plain}]({url})"
        return plain
    # compact のラベル部分を AI の title 表記に寄せる（表記ゆれ許容）
    m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)(.*)$", link)
    if m:
        return f"[{plain}]({m.group(2)}){m.group(3)}"
    return link


def enrich_hot_topics_with_links(
    editorial: Dict[str, Any],
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """hot_topics に機械由来の link_line を付与（LLM に URL を出させない）。"""
    index = build_hot_topic_link_index(weekly_rising, weekly_category)
    enriched: List[Dict[str, Any]] = []
    for t in editorial.get("hot_topics") or []:
        if not isinstance(t, dict):
            continue
        title = str(t.get("title") or "").strip()
        why = str(t.get("why") or "").strip()
        if not title or not why:
            continue
        plain = _strip_md_link_title(title)
        matched = index.get(plain.casefold())
        row: Dict[str, Any] = {"title": plain, "why": why}
        if matched:
            row["link_line"] = _hot_topic_heading_line(plain, matched)
            if matched.get("url"):
                row["url"] = matched.get("url")
        else:
            row["link_line"] = plain
        enriched.append(row)
    out = dict(editorial)
    out["hot_topics"] = enriched
    return out


def render_weekly_rising_markdown(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
) -> str:
    heading = (
        "## 📈 Biggest movers last week"
        if _ACTIVE_REGION == "us"
        else _WEEKLY_RISING_HEADING
    )
    empty_msg = (
        "(No big rank movers last week.)"
        if _ACTIVE_REGION == "us"
        else "（先週、順位が大きく動いた話題は見つかりませんでした）"
    )
    lines: List[str] = [heading, ""]
    any_items = False
    single_region = len(WEEKLY_REGIONS) == 1
    for region in WEEKLY_REGIONS:
        items = weekly_rising.get(region) or []
        if not single_region:
            lines.append(f"### {WEEKLY_REGION_LABELS[region]}")
            lines.append("")
        if not items:
            lines.append(empty_msg)
            lines.append("")
            continue
        any_items = True
        it = items[0]
        link = _compact_weekly_link_line(it)
        lines.append(f"1. {link}")
        lines.append("")
        movement = format_weekly_rising_movement_block(it)
        if movement:
            lines.append(movement.rstrip())
        lines.append("")
    if not any_items:
        return f"{heading}\n\n{empty_msg}\n"
    return "\n".join(lines).rstrip() + "\n"


def render_weekly_cross_markdown(
    weekly_cross: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines: List[str] = [_WEEKLY_CROSS_HEADING, ""]
    any_items = False
    for region in WEEKLY_REGIONS:
        items = weekly_cross.get(region) or []
        lines.append(f"### {WEEKLY_REGION_LABELS[region]}")
        lines.append("")
        if not items:
            lines.append("（週を通じて複数ソースにまたがった同一トピックはありませんでした）")
            lines.append("")
            continue
        any_items = True
        for i, it in enumerate(items, 1):
            label = str(it.get("label") or "").strip() or "（ラベル不明）"
            lines.append(f"#### {i}. {label}")
            lines.append("")
            days = it.get("days") or []
            meta_parts: List[str] = []
            if days:
                meta_parts.append(f"**{len(days)}日**")
            sources = (it.get("sources_display") or "").strip()
            if sources:
                meta_parts.append(sources)
            if meta_parts:
                lines.append("> " + " · ".join(meta_parts))
                lines.append("")
            rank_by_day = it.get("rank_evidence_by_day") or {}
            table = format_weekly_rank_table(rank_by_day)
            if table:
                lines.append(table)
                lines.append("")
    if not any_items:
        return (
            f"{_WEEKLY_CROSS_HEADING}\n\n"
            "（週を通じて複数ソースにまたがった同一トピックはありませんでした）\n"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_data_premise(meta: Dict[str, Any]) -> str:
    missing_snap = meta.get("missing_snapshot_dates") or []
    partial = meta.get("partial_snapshot_dates") or []
    if not missing_snap and not partial:
        return ""
    lines = ["## データ前提", ""]
    if missing_snap:
        lines.append(f"- スナップショット欠損日: {', '.join(missing_snap)}")
    if partial:
        lines.append(f"- スナップショット部分欠損（スロット欠け）: {', '.join(partial)}")
    return "\n".join(lines).rstrip() + "\n"


def parse_editorial_json(raw: str) -> Dict[str, Any]:
    text = strip_wrapping_fences(raw)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("editorial JSON must be an object")

    flow_jp = str(data.get("flow_jp") or data.get("flow") or "").strip()
    flow_us = str(data.get("flow_us") or data.get("flow") or "").strip()
    # 地域別キーがあれば優先。単一 region 生成では flow も受け付ける。
    if _ACTIVE_REGION == "us":
        if not flow_us and not flow_jp:
            raise ValueError("editorial JSON missing flow_us / flow")
        if not flow_us:
            flow_us = flow_jp
    else:
        if not flow_jp:
            raise ValueError("editorial JSON missing flow_jp / flow")

    hot_raw = data.get("hot_topics") or []
    hot_topics: List[Dict[str, str]] = []
    if isinstance(hot_raw, list):
        for h in hot_raw[:WEEKLY_HOT_MAX]:
            if not isinstance(h, dict):
                continue
            title = str(h.get("title") or h.get("label") or "").strip()
            why = str(h.get("why") or h.get("reason") or "").strip()
            if title and why:
                hot_topics.append({"title": title, "why": why})

    next_raw = data.get("next_week") or data.get("next_week_points") or []
    next_week: List[str] = []
    if isinstance(next_raw, list):
        for p in next_raw:
            s = str(p or "").strip()
            if s:
                next_week.append(s)
        next_week = next_week[:WEEKLY_NEXT_MAX]

    return {
        "flow_jp": flow_jp,
        "flow_us": flow_us,
        "hot_topics": hot_topics,
        "next_week": next_week,
        "category_themes": {
            "jp": _parse_category_themes_region(data, "category_themes_jp"),
            "us": _parse_category_themes_region(data, "category_themes_us"),
        },
    }


def render_weekly_hot_topics_markdown(editorial: Dict[str, Any]) -> str:
    topics = editorial.get("hot_topics") or []
    if _ACTIVE_REGION == "us":
        heading = _WEEKLY_HOT_HEADING_US
        empty = "(No hot topics selected last week.)"
    else:
        heading = _WEEKLY_HOT_HEADING
        empty = "（先週のホットトピックはありません）"
    lines: List[str] = [heading, ""]
    if not topics:
        lines.append(empty)
        return "\n".join(lines).rstrip() + "\n"
    for i, t in enumerate(topics, 1):
        why = str(t.get("why") or "").strip()
        heading_line = str(t.get("link_line") or t.get("title") or "").strip()
        lines.append(f"### {i}. {heading_line}")
        lines.append("")
        lines.append(why)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_weekly_next_week_markdown(editorial: Dict[str, Any]) -> str:
    points = editorial.get("next_week") or []
    if _ACTIVE_REGION == "us":
        heading = _WEEKLY_NEXT_HEADING_US
        empty = "(No carry-over points.)"
    else:
        heading = _WEEKLY_NEXT_HEADING
        empty = "（来週に残る論点はありません）"
    lines: List[str] = [heading, ""]
    if not points:
        lines.append(empty)
        return "\n".join(lines).rstrip() + "\n"
    for p in points:
        lines.append(f"- {p}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_teaser_from_weekly_preview_lead(
    preview_lead: str, max_chars: int = 90
) -> str:
    from services.summary.daily_summary_preview import clamp_teaser, first_sentence

    return clamp_teaser(first_sentence(preview_lead), max_chars=max_chars)


def build_mechanical_weekly_preview_lead(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> str:
    """週次 Web プレビュー用: 急上昇 top1 → ニュース区分 top1 の順で機械リード。"""
    region = WEEKLY_REGIONS[0]
    rising = weekly_rising.get(region) or []
    if rising:
        it = rising[0]
        label = str(it.get("label") or "").strip()
        if label:
            dc = int(it.get("day_count") or len(it.get("days") or []) or 0)
            if _ACTIVE_REGION == "us":
                days_bit = f" across {dc} day(s)" if dc else ""
                return (
                    f'Last week, "{label}" showed the largest rank jump on the dashboard{days_bit}.'
                )
            days_bit = f"（{dc}日）" if dc else ""
            return f"先週、順位の動きが最も大きかったのは「{label}」{days_bit}。"

    for block in weekly_category.get(region) or []:
        if str(block.get("category") or "") != "ニュース":
            continue
        items = block.get("items") or []
        if not items:
            continue
        label = str(items[0].get("label") or "").strip()
        if label:
            if _ACTIVE_REGION == "us":
                return f'News category leader last week: "{label}".'
            return f"先週、ニュース区分で目立ったのは「{label}」。"
    if _ACTIVE_REGION == "us":
        return "Last week's category leaders and rank movers are listed below."
    return "先週のカテゴリ別トップと順位の動きは以下のとおり。"



def _is_appstore_series(series_key: str) -> bool:
    return weekly_series_weight(series_key) <= 0


def build_mechanical_weekly_flow(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
) -> str:
    """LLM なしの「先週の流れ」短文。rising top + カテゴリ上位ラベル。"""
    region = WEEKLY_REGIONS[0]
    bits: List[str] = []
    rising = weekly_rising.get(region) or []
    if rising:
        it = rising[0]
        label = str(it.get("label") or "").strip()
        dc = int(it.get("day_count") or len(it.get("days") or []) or 0)
        if label:
            if _ACTIVE_REGION == "us":
                days_bit = f" across {dc} day(s)" if dc else ""
                bits.append(
                    f'The sharpest rank move last week was "{label}"{days_bit}.'
                )
            else:
                days_bit = f"（{dc}日）" if dc else ""
                bits.append(f"順位の動きが最も大きかったのは「{label}」{days_bit}。")
    labels: List[str] = []
    for block in weekly_category.get(region) or []:
        for it in block.get("items") or []:
            lab = str(it.get("label") or "").strip()
            sk = str(it.get("series_key") or "")
            if not lab or _is_appstore_series(sk):
                continue
            if lab in labels:
                continue
            labels.append(lab)
            if len(labels) >= 3:
                break
        if len(labels) >= 3:
            break
    if labels:
        if _ACTIVE_REGION == "us":
            joined = ", ".join(f'"{x}"' for x in labels)
            bits.append(f"Category leaders included {joined}.")
        else:
            bits.append("カテゴリ上位には「" + "」「".join(labels) + "」などが入った。")
    if bits:
        return " ".join(bits)
    if _ACTIVE_REGION == "us":
        return "Last week's category leaders and rank movers are summarized below."
    return "先週のカテゴリ別トップと順位の動きは以下のとおり。"


def build_mechanical_weekly_hot_topics(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
    *,
    limit: int = WEEKLY_HOT_MAX,
) -> List[Dict[str, str]]:
    """カテゴリ digest から機械ホットトピックを抽出（App Store 除外）。"""
    region = WEEKLY_REGIONS[0]
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for block in weekly_category.get(region) or []:
        cat = str(block.get("category") or "")
        for it in block.get("items") or []:
            label = str(it.get("label") or "").strip()
            sk = str(it.get("series_key") or "")
            if not label or _is_appstore_series(sk):
                continue
            nk = sr.normalize_label_key(label)
            if nk in seen:
                continue
            seen.add(nk)
            day_count = int(it.get("day_count") or len(it.get("days") or []) or 0)
            cross = bool(it.get("cross_source"))
            score = int(it.get("weekly_score") or 0) or (
                day_count * 10 + (15 if cross else 0) + weekly_series_weight(sk)
            )
            candidates.append(
                {
                    "title": label,
                    "day_count": day_count,
                    "cross_source": cross,
                    "category": cat,
                    "best_rank": it.get("best_rank"),
                    "score": score,
                    "link_line": it.get("link_line") or "",
                    "url": it.get("url"),
                }
            )
    # rising を補完
    for it in weekly_rising.get(region) or []:
        label = str(it.get("label") or "").strip()
        sk = str(it.get("series_key") or "")
        if not label or _is_appstore_series(sk):
            continue
        nk = sr.normalize_label_key(label)
        if nk in seen:
            continue
        seen.add(nk)
        day_count = int(it.get("day_count") or len(it.get("days") or []) or 0)
        candidates.append(
            {
                "title": label,
                "day_count": day_count,
                "cross_source": bool(it.get("cross_source")),
                "category": str(it.get("category") or ""),
                "best_rank": it.get("best_rank"),
                "score": int(it.get("weekly_score") or 0) or day_count * 10,
                "link_line": it.get("link_line") or "",
                "url": it.get("url"),
            }
        )
    candidates.sort(key=lambda x: (-int(x["score"]), -int(x["day_count"]), str(x["title"])))
    out: List[Dict[str, str]] = []
    for c in candidates[: max(0, limit)]:
        dc = int(c["day_count"])
        if _ACTIVE_REGION == "us":
            why_bits = []
            if dc:
                why_bits.append(f"appeared on {dc} day(s)")
            if c["cross_source"]:
                why_bits.append("crossed multiple sources")
            if c.get("best_rank"):
                why_bits.append(f"best rank {c['best_rank']}")
            if c.get("category"):
                why_bits.append(f"category {c['category']}")
            why = "; ".join(why_bits) + "." if why_bits else "Stood out in last week's digest."
        else:
            why_bits = []
            if dc:
                why_bits.append(f"{dc}日登場")
            if c["cross_source"]:
                why_bits.append("複数ソースで重なった")
            if c.get("best_rank"):
                why_bits.append(f"最高順位 {c['best_rank']}")
            if c.get("category"):
                why_bits.append(f"区分 {c['category']}")
            why = "。".join(why_bits) + "。" if why_bits else "先週の digest で目立った話題。"
        row: Dict[str, str] = {"title": str(c["title"]), "why": why}
        if c.get("link_line"):
            row["link_line"] = str(c["link_line"])
        if c.get("url"):
            row["url"] = str(c["url"])
        out.append(row)
    return out


def assemble_weekly_markdown(
    iso_week: str,
    mon: date,
    sun: date,
    editorial: Dict[str, Any],
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_category: Dict[str, List[Dict[str, Any]]],
    meta: Dict[str, Any],
    *,
    include_flow: bool = False,
    include_hot_topics: bool = False,
    include_next_week: bool = False,
) -> str:
    if include_hot_topics:
        editorial = enrich_hot_topics_with_links(editorial, weekly_rising, weekly_category)
    if _ACTIVE_REGION == "us":
        title = f"# Weekly summary — {iso_week} (observation week JST {mon.isoformat()}–{sun.isoformat()})"
        meta_lines = [
            f"- **Week**: {mon.isoformat()} – {sun.isoformat()} (JST)",
            "",
        ]
    else:
        title = f"# 週次サマリー — {iso_week}（対象週 JST {mon.isoformat()}〜{sun.isoformat()}）"
        meta_lines = [
            f"- **対象週**: {mon.isoformat()} 〜 {sun.isoformat()}",
            "",
        ]

    lines: List[str] = [title, *meta_lines]
    # 1) オープナー（配信週カレンダー・先週マーケット・ひと息）
    try:
        from services.summary.morning_brief import render_weekly_brief_markdown

        brief = render_weekly_brief_markdown(mon, sun, _ACTIVE_REGION)
        if brief:
            lines.append(brief.rstrip())
            lines.append("")
    except Exception as exc:
        # オープナー失敗で本文全体を落とさない
        meta.setdefault("brief_warnings", []).append(str(exc))
    # 2) 先週の流れ → 動いた話題 → ホット → カテゴリ
    body_parts: List[str] = []
    if include_flow:
        if _ACTIVE_REGION == "us":
            flow_text = (
                editorial.get("flow_us")
                or editorial.get("flow_jp")
                or "(Could not generate the U.S. weekly brief.)"
            ).strip()
            body_parts.append("## Last week in review\n\n" + flow_text)
        else:
            flow_text = (
                editorial.get("flow_jp")
                or "（日本向けの週次要約を生成できませんでした）"
            ).strip()
            body_parts.append("## 先週の流れ（短文）\n\n" + flow_text)
    body_parts.append(render_weekly_rising_markdown(weekly_rising).rstrip())
    if include_hot_topics:
        body_parts.append(render_weekly_hot_topics_markdown(editorial).rstrip())
    if include_next_week:
        body_parts.append(render_weekly_next_week_markdown(editorial).rstrip())
    body_parts.append(
        render_weekly_category_markdown(weekly_category, editorial).rstrip()
    )
    lines.extend(p + "\n" for p in body_parts if p)
    premise = render_data_premise(meta)
    if premise:
        lines.append(premise.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def call_openai(
    system: str,
    user: str,
    api_key: str,
    model: str,
    timeout: int = 180,
    *,
    json_mode: bool = False,
) -> str:
    body: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.35,
        "max_tokens": 4096,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    if not r.ok:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:2000]}")
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenAI response missing choices: {str(data)[:2000]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not content or not isinstance(content, str):
        raise RuntimeError("OpenAI response missing message.content")
    return content.strip()


def strip_wrapping_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def merge_front_matter(
    iso_week: str,
    mon: date,
    sun: date,
    model: str,
    inner_markdown: str,
    meta: Dict[str, Any],
    *,
    teaser: str = "",
    preview_lead: str = "",
    generator: str = "mechanical",
) -> str:
    gen_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    range_s = f"{mon.isoformat()} 〜 {sun.isoformat()}"
    n_found = sum(1 for x in meta.get("daily_files", []) if x.get("found"))
    snap_found = meta.get("snapshot_days_found", 0)
    teaser_line = ""
    if teaser:
        escaped = teaser.replace("\\", "\\\\").replace('"', '\\"')
        teaser_line = f'teaser: "{escaped}"\n'
    preview_line = ""
    if preview_lead:
        escaped = preview_lead.replace("\\", "\\\\").replace('"', '\\"')
        preview_line = f'preview_lead: "{escaped}"\n'
    model_line = f'model: "{model}"\n' if model else ""
    fm = f"""---
status: draft
iso_week: "{iso_week}"
week_range_jst: "{range_s}"
reviewer: ""
reviewed_at: ""
generator: {generator}
{model_line}region: "{_ACTIVE_REGION}"
input_mode: "{meta.get('input_mode', 'snapshots')}"
snapshot_days_found: {snap_found}
snapshot_days_expected: 7
missing_snapshot_dates: {json.dumps(meta.get('missing_snapshot_dates') or [], ensure_ascii=False)}
partial_snapshot_dates: {json.dumps(meta.get('partial_snapshot_dates') or [], ensure_ascii=False)}
daily_files_found: {n_found}
daily_files_expected: 7
missing_daily_dates: {json.dumps(meta.get('missing_dates') or [], ensure_ascii=False)}
generated_at: "{gen_at}"
{teaser_line}{preview_line}---

"""
    body = strip_wrapping_fences(inner_markdown)
    return fm + body


EDITORIAL_SYSTEM_PROMPT = """あなたはトレンドダッシュボードの週次サマリー編集者だ。
入力 JSON の weekly_mechanical.regions.jp.weekly_category_pool がカテゴリ別候補の正本。
各候補は「その週のうち1日以上、日次カテゴリ top3 に入ったラベル」。
daily_summaries があれば補助。新しい URL・ラベル・事実を捏造しない。

この原稿は **日本ページ向け**（日本ソースのみ）。アメリカソースは扱わない。

weekly_rising は「週内で最もジャンプした1件」の参考程度（横ばい・悪化のみの話題は除外済み）。
Twitch 等の定番ゲーム配信だけで flow を書かない（カテゴリ pool を優先）。

カテゴリ別 top3 の一覧は **機械生成**（候補 label をそのままリンク表示）する。
flow では pool の **具体ラベル・固有名詞** をそのまま引用すること。
「エンタメの話題」「トレンドの検索」「新技術の導入」のような抽象表現は禁止。

**出力は JSON オブジェクトのみ**（Markdown 不可）。キー:
- `flow_jp` (string): 5〜8文・日本語。**先週としての1本のストーリー**（カテゴリ1位の列挙にしない）。
  読者向けには「先週」と書く（「今週」は使わない）。続いた話題・一過性の話題の対比があるとよい。pool の label を具体名で引用。
- `hot_topics` (array): 最大5件。各要素 `{ "title", "why" }`。
  title は pool / rising の具体ラベル（URL・Markdown リンクは付けない。リンクは後段で機械付与）。
  why は2〜4文で「なぜその週ホットか」（ラベル文言は不要・本文のみ）。
  定番株・一過性の季節ネタ・事故の単日首位だけは避ける。厳選すること。
- `next_week` (array of string): 2〜3件。来週も残りうる論点（各1〜2文）。未来の断定予測は禁止。

禁止: 入力に無いラベル・URL・未来予測・Markdown 見出し・抽象カテゴリ名だけの記述。"""


EDITORIAL_SYSTEM_PROMPT_US = """You are the weekly-brief editor for the Trends Dashboard (U.S. page).
The source of truth is weekly_mechanical.regions.us.weekly_category_pool in the input JSON.
Each candidate label appeared in the daily category top3 on at least one day that week.
daily_summaries are optional assist context. Do not invent URLs, labels, or facts.

This brief is **U.S. page only** (U.S. sources). Do not summarize Japan-only sources.

weekly_rising is only a hint (the single biggest jump of the week; flat/worsening-only are excluded).
Do not write the flow around evergreen Twitch titles alone; prefer the category pool.

Category top3 lists are machine-generated (labels shown as links).
In flow, quote concrete labels/proper nouns from the pool.
Ban vague phrases like "entertainment topics" or "tech adoption" without labels.

**Output JSON only** (no Markdown). Keys:
- `flow_us` (string): 5–8 sentences in **English**. One narrative arc for **last week** (not a list of daily #1s).
  Use "last week" (not "this week"). Contrast what persisted vs one-off spikes. Quote pool labels by name.
- `hot_topics` (array): up to 5 items `{ "title", "why" }`.
  title = concrete pool/rising label (no URL/Markdown link; links are attached mechanically later).
  why = 2–4 sentences on why it was hot (body only; no "Why hot:" label).
  Skip evergreen tickers and one-day accident spikes. Be selective.
- `next_week` (array of string): 2–3 carry-over points (1–2 sentences each). No hard forecasts.

Forbidden: labels/URLs not in input, forecasts, Markdown headings, abstract category-only prose."""


LEGACY_SYSTEM_PROMPT = """あなたはトレンドダッシュボードの編集者だ。入力は、ある1週間（ISO 週・月曜始まり）
の各日について、すでにリポジトリに存在する「日次サマリー」Markdown の本文だけである。
各日の見出し日付（YYYY-MM-DD）は **その日のトレンド観測日（business_day）** であり、
ファイルが週のあとに生成されたこととは無関係に扱う。
新たに Web やトレンド API を参照したり、スナップショットを読んだりしない。

次を厳守すること:
- 出力は日本語の Markdown のみ（YAML フロントマターは書かない。先頭から # 見出しでよい）。
- 見出し構造:
  - `# 週次サマリー — ISO_WEEK（対象週 JST WEEK_MON〜WEEK_SUN）`
  - `- **対象週**:` 1行（タイトルと重複するがスキャン用に残す）
  - `## 先週の流れ（短文）`
- 「先週の流れ」は日次の繰り返しにせず、週としての要約にする。
- 日次ファイルが欠けている日がある場合は `## データ前提` を短く置く。
- 憶測・未確認の断定は避ける。"""


def run_generate_snapshots(
    week_mon: date,
    api_key: str,
    model: str,
    daily_dir: Path,
    *,
    via_http: bool,
    database_url: str,
    base_url: str,
    connect_timeout: int,
    request_timeout: int,
) -> Tuple[str, Dict[str, Any]]:
    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)

    snap_meta, weekly_rising, weekly_cross, weekly_category = build_week_snapshot_rollups(
        week_mon,
        via_http=via_http,
        database_url=database_url,
        base_url=base_url,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout,
    )
    daily_text, daily_meta = build_daily_rollups(week_mon, week_sun, daily_dir)
    meta: Dict[str, Any] = {**snap_meta, **daily_meta}
    meta["iso_week"] = stem
    meta["input_mode"] = "snapshots"

    if meta.get("snapshot_days_found", 0) == 0:
        meta["error"] = "no_snapshot_days"
        return "", meta

    mechanical = build_mechanical_llm_payload(weekly_rising, weekly_cross, weekly_category)
    header = {
        "iso_week": stem,
        "week_mon_jst": week_mon.isoformat(),
        "week_sun_jst": week_sun.isoformat(),
        "missing_snapshot_dates": meta.get("missing_snapshot_dates"),
        "partial_snapshot_dates": meta.get("partial_snapshot_dates"),
        "missing_daily_dates": meta.get("missing_dates"),
        "weekly_mechanical": mechanical,
    }
    user_parts = [json.dumps(header, ensure_ascii=False, indent=2)]
    if daily_text.strip():
        user_parts.append(
            "\n--- 以下、日次サマリー Markdown（補助。欠損あり） ---\n\n" + daily_text
        )
    user = "\n".join(user_parts)
    system = EDITORIAL_SYSTEM_PROMPT_US if _ACTIVE_REGION == "us" else EDITORIAL_SYSTEM_PROMPT
    raw = call_openai(system, user, api_key, model, json_mode=True)
    editorial = parse_editorial_json(raw)
    warnings: List[str] = []
    for region in WEEKLY_REGIONS:
        if len(weekly_rising.get(region) or []) == 0:
            warnings.append(f"weekly_rising_{region} empty")
    if warnings:
        meta["editorial_warning"] = "; ".join(warnings)

    inner = assemble_weekly_markdown(
        stem,
        week_mon,
        week_sun,
        editorial,
        weekly_rising,
        weekly_category,
        meta,
        include_flow=False,
        include_hot_topics=False,
        include_next_week=False,
    )
    meta["model"] = model
    meta["generator"] = "openai"
    flow_text = (
        str(editorial.get("flow_us") or editorial.get("flow_jp") or "").strip()
        if _ACTIVE_REGION == "us"
        else str(editorial.get("flow_jp") or "").strip()
    )
    teaser = build_teaser_from_weekly_preview_lead(flow_text) if flow_text else ""
    full = merge_front_matter(
        stem,
        week_mon,
        week_sun,
        model,
        inner,
        meta,
        teaser=teaser,
        preview_lead=flow_text,
        generator="openai",
    )
    return full, meta


def run_generate_mechanical(
    week_mon: date,
    daily_dir: Path,
    *,
    via_http: bool,
    database_url: str,
    base_url: str,
    connect_timeout: int,
    request_timeout: int,
) -> Tuple[str, Dict[str, Any]]:
    """OpenAI 不使用。スナップショットから機械的に週次 Markdown を組み立てる。"""
    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)

    snap_meta, weekly_rising, weekly_cross, weekly_category = build_week_snapshot_rollups(
        week_mon,
        via_http=via_http,
        database_url=database_url,
        base_url=base_url,
        connect_timeout=connect_timeout,
        request_timeout=request_timeout,
    )
    _ = weekly_cross
    _, daily_meta = build_daily_rollups(week_mon, week_sun, daily_dir)
    meta: Dict[str, Any] = {**snap_meta, **daily_meta}
    meta["iso_week"] = stem
    meta["input_mode"] = "snapshots"
    meta["generator"] = "mechanical"

    if meta.get("snapshot_days_found", 0) == 0:
        meta["error"] = "no_snapshot_days"
        return "", meta

    flow = build_mechanical_weekly_flow(weekly_rising, weekly_category)
    hot_topics = build_mechanical_weekly_hot_topics(weekly_rising, weekly_category)
    editorial: Dict[str, Any] = {
        "flow_jp": flow if _ACTIVE_REGION != "us" else "",
        "flow_us": flow if _ACTIVE_REGION == "us" else "",
        "hot_topics": hot_topics,
        "next_week": [],
        "category_themes": {"jp": {}, "us": {}},
    }
    preview_lead = build_mechanical_weekly_preview_lead(weekly_rising, weekly_category)
    teaser = build_teaser_from_weekly_preview_lead(preview_lead)

    inner = assemble_weekly_markdown(
        stem,
        week_mon,
        week_sun,
        editorial,
        weekly_rising,
        weekly_category,
        meta,
        include_flow=True,
        include_hot_topics=True,
        include_next_week=False,
    )
    warnings: List[str] = []
    for region in WEEKLY_REGIONS:
        if len(weekly_rising.get(region) or []) == 0:
            warnings.append(f"weekly_rising_{region} empty")
    if warnings:
        meta["editorial_warning"] = "; ".join(warnings)
    meta["preview_lead_source"] = "mechanical"
    meta["teaser_source"] = "mechanical"
    full = merge_front_matter(
        stem,
        week_mon,
        week_sun,
        "",
        inner,
        meta,
        teaser=teaser,
        preview_lead=preview_lead,
        generator="mechanical",
    )
    return full, meta


def run_generate_daily_only(
    week_mon: date,
    api_key: str,
    model: str,
    daily_dir: Path,
) -> Tuple[str, Dict[str, Any]]:
    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)
    roll, meta = build_daily_rollups(week_mon, week_sun, daily_dir)
    meta["iso_week"] = stem
    meta["input_mode"] = "daily_only"

    n_found = sum(1 for x in meta.get("daily_files", []) if x.get("found"))
    if n_found == 0:
        meta["error"] = "no_daily_files"
        return "", meta

    header = json.dumps(
        {
            "iso_week": stem,
            "week_mon_jst": week_mon.isoformat(),
            "week_sun_jst": week_sun.isoformat(),
            "missing_daily_dates": meta.get("missing_dates", []),
        },
        ensure_ascii=False,
    )
    user = f"{header}\n\n--- 以下、日次サマリー本文 ---\n\n{roll}"
    inner = call_openai(LEGACY_SYSTEM_PROMPT, user, api_key, model)
    meta["model"] = model
    full = merge_front_matter(stem, week_mon, week_sun, model, inner, meta)
    return full, meta


def openai_api_key() -> str:
    """OPENAI_API_KEY を優先。ローカル .env の OPEN_API_KEY も受け付ける。"""
    return (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY") or "").strip()


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv()
    p = argparse.ArgumentParser(
        description="Generate weekly AI summary from trend_daily_snapshots (default) or daily Markdown"
    )
    p.add_argument(
        "--weekly-for-date",
        metavar="YYYY-MM-DD",
        help="Summarize the ISO week containing this date (default: last completed week, JST)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Without API key: print manifest. With key: print markdown",
    )
    p.add_argument("--write", action="store_true", help="Write docs/summaries/weekly/{ISO}.md")
    p.add_argument("--force", action="store_true", help="Overwrite existing file")
    p.add_argument(
        "--region",
        choices=("jp", "us"),
        default="jp",
        help="jp → weekly/ (Japanese). us → weekly/us/ (English)",
    )
    p.add_argument(
        "--daily-only",
        action="store_true",
        help="Legacy: use daily Markdown only (no snapshots)",
    )
    p.add_argument(
        "--from-api",
        action="store_true",
        help="Fetch snapshots via TREND_DASHBOARD_BASE_URL (CI / no DATABASE_URL)",
    )
    p.add_argument("--base-url", default=None, help="Override TREND_DASHBOARD_BASE_URL")
    p.add_argument(
        "--daily-dir",
        type=Path,
        default=None,
        help="Override daily summaries directory",
    )
    p.add_argument("--connect-timeout", type=int, default=20)
    p.add_argument("--request-timeout", type=int, default=120)
    p.add_argument(
        "--use-llm",
        action="store_true",
        help="Use OpenAI for flow/hot/next_week (default: mechanical only, no API key)",
    )
    args = p.parse_args()
    configure_weekly_region(args.region)

    if args.weekly_for_date:
        anchor = date.fromisoformat(args.weekly_for_date)
        week_mon, _ = week_range_mon_sun(anchor)
    else:
        week_mon = default_week_mon_jst()

    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)
    daily_dir = weekly_daily_assist_dir(args.daily_dir)

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    api_key = openai_api_key()
    model = (os.getenv("OPENAI_SUMMARY_MODEL") or "gpt-4o-mini").strip()
    base_url = (args.base_url or os.getenv("TREND_DASHBOARD_BASE_URL") or BASE_DEFAULT).rstrip(
        "/"
    )
    via_http = use_http_snapshots(cli_from_api=args.from_api, database_url=database_url)

    if not args.daily_only and via_http and not args.from_api:
        print(
            "NOTE: using /api/summaries/daily-snapshots (same as --from-api).",
            file=sys.stderr,
        )

    if args.dry_run and args.use_llm and not api_key:
        if args.daily_only:
            _, meta = build_daily_rollups(week_mon, week_sun, daily_dir)
            print(json.dumps(meta, ensure_ascii=False, indent=2))
        else:
            if via_http or database_url:
                try:
                    snap_meta, rising, cross, category = build_week_snapshot_rollups(
                        week_mon,
                        via_http=via_http,
                        database_url=database_url,
                        base_url=base_url,
                        connect_timeout=args.connect_timeout,
                        request_timeout=args.request_timeout,
                    )
                    _, daily_meta = build_daily_rollups(week_mon, week_sun, daily_dir)
                    meta = {**snap_meta, **daily_meta}
                    meta["weekly_rising_preview"] = rising
                    meta["weekly_cross_preview"] = cross
                    meta["weekly_category_preview"] = category
                    print(json.dumps(meta, ensure_ascii=False, indent=2))
                except Exception as exc:
                    print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
                    return 1
            else:
                print(
                    json.dumps(
                        {"error": "set DATABASE_URL or use --from-api"},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 1
        print("\n(set OPENAI_API_KEY to generate weekly markdown)", file=sys.stderr)
        return 0

    if args.daily_only:
        if not args.use_llm or not api_key:
            print(
                "❌ --daily-only は --use-llm と OPENAI_API_KEY が必要です",
                file=sys.stderr,
            )
            return 1
        text, meta = run_generate_daily_only(week_mon, api_key, model, daily_dir)
        err = meta.get("error")
        if err == "no_daily_files":
            print(
                f"❌ {week_mon.isoformat()}〜{week_sun.isoformat()} の日次 Markdown が見つかりません。",
                file=sys.stderr,
            )
            return 2
    else:
        if not via_http and not database_url:
            print(
                "❌ DATABASE_URL が未設定です（Fly 外では --from-api を使う）",
                file=sys.stderr,
            )
            return 1
        try:
            if args.use_llm:
                if not api_key:
                    print(
                        "❌ --use-llm には OPENAI_API_KEY が必要です",
                        file=sys.stderr,
                    )
                    return 1
                text, meta = run_generate_snapshots(
                    week_mon,
                    api_key,
                    model,
                    daily_dir,
                    via_http=via_http,
                    database_url=database_url,
                    base_url=base_url,
                    connect_timeout=args.connect_timeout,
                    request_timeout=args.request_timeout,
                )
            else:
                text, meta = run_generate_mechanical(
                    week_mon,
                    daily_dir,
                    via_http=via_http,
                    database_url=database_url,
                    base_url=base_url,
                    connect_timeout=args.connect_timeout,
                    request_timeout=args.request_timeout,
                )
        except (requests.RequestException, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(f"❌ 週次生成失敗: {exc}", file=sys.stderr)
            return 1
        if meta.get("error") == "no_snapshot_days":
            print(
                f"❌ {week_mon.isoformat()}〜{week_sun.isoformat()} のスナップショットがありません。",
                file=sys.stderr,
            )
            return 2

    if args.dry_run:
        print(text)
        return 0

    if not args.write:
        print(text)
        return 0

    out = weekly_output_dir() / f"{stem}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        print(f"skip (exists): {out.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 0

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
