#!/usr/bin/env python3
"""
直前に終了した ISO 週（月〜日）の trend_daily_snapshots を集計し、
OpenAI で週次サマリー（今週の流れ・急上昇・クロスソース）を1ファイルに生成する。

既定入力は **スナップショット**（DB 直読 or ``--from-api``）。日次 Markdown は
補助コンテキストとして読む（欠損可）。``--daily-only`` で旧挙動（日次 md のみ）。

  export OPENAI_API_KEY=sk-...
  python scripts/generate_ai_weekly_summary.py --from-api --dry-run
  python scripts/generate_ai_weekly_summary.py --from-api --write --force

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
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import snapshot_rising as sr

DAILY_DIR = REPO_ROOT / "docs" / "summaries" / "daily"
WEEKLY_DIR = REPO_ROOT / "docs" / "summaries" / "weekly"
BASE_DEFAULT = "https://trends-dashboard.fly.dev"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_USER_CHARS = 100_000
EXPECTED_SLOTS = ("01", "07", "13", "19")
WEEKLY_RISING_PER_REGION = 3
WEEKLY_CROSS_PER_REGION = 3
WEEKLY_REGIONS = ("jp", "us")
WEEKLY_REGION_LABELS = {"jp": "🇯🇵 日本", "us": "🇺🇸 アメリカ"}
# 週次 rising スコア（jump 同率時の tie-break 用）
WEEKLY_SCORE_DAY = 10
WEEKLY_SCORE_SLOT = 5
WEEKLY_SCORE_JUMP = 1.0
WEEKLY_SCORE_CROSS = 25

_WEEKLY_RISING_HEADING = "## 📈 今週いちばん動いた話題"
_WEEKLY_CROSS_HEADING = "## 複数ソースで週を通じて重なった話題"

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
    "medium_",
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
    "openalex_",
    "book_",
)


def weekly_series_weight(series_key: str) -> int:
    """週次 rising 用: 系列の読者向け重要度（大きいほど優先）。"""
    sk = (series_key or "").strip().lower()
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
) -> Tuple[Dict[str, Any], Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    """7日分スナップショットを読み、地域別の週次急上昇・クロスソース集計とメタを返す。"""
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

    weekly_rising: Dict[str, List[Dict[str, Any]]] = {}
    weekly_cross: Dict[str, List[Dict[str, Any]]] = {}
    for region in WEEKLY_REGIONS:
        cross_keys = cross_label_keys_from_daily(daily_cross_by_region_day[region])
        weekly_rising[region] = aggregate_weekly_rising(
            daily_rising_by_region_day[region],
            count=WEEKLY_RISING_PER_REGION,
            cross_label_keys=cross_keys,
        )
        weekly_cross[region] = aggregate_weekly_cross_source(
            daily_cross_by_region_day[region],
            count=WEEKLY_CROSS_PER_REGION,
        )
        for item in weekly_rising[region]:
            item["region"] = region
        for item in weekly_cross[region]:
            item["region"] = region

    meta["snapshot_days_found"] = sum(1 for x in meta["snapshot_days"] if x.get("found"))
    meta["weekly_rising_counts"] = {r: len(weekly_rising[r]) for r in WEEKLY_REGIONS}
    meta["weekly_cross_counts"] = {r: len(weekly_cross[r]) for r in WEEKLY_REGIONS}
    return meta, weekly_rising, weekly_cross


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
            agg = by_label.get(nk)
            if agg is None:
                agg = {
                    "label": label,
                    "days": set(),
                    "jump_sum": 0.0,
                    "slot_obs": 0,
                    "best_rank": 999,
                    "series_weight": sw,
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


def build_mechanical_llm_payload(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_cross: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """LLM 向けに地域別の週次機械集計を JSON 化。"""
    regions: Dict[str, Any] = {}
    for region in WEEKLY_REGIONS:
        regions[region] = {
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


def format_weekly_rising_summary_line(item: Dict[str, Any]) -> str:
    """1行サマリー（出現・jump・スコア・区分）。"""
    days = item.get("days") or []
    parts: List[str] = []
    if days:
        parts.append(f"**{len(days)}日**")
    jump = item.get("jump_sum")
    if jump is not None:
        parts.append(f"jump **+{jump}**")
    score = item.get("weekly_score")
    if score is not None:
        parts.append(f"スコア **{score}**")
    if item.get("cross_source"):
        parts.append("複数ソース")
    cat = (item.get("category") or "").strip()
    if cat:
        parts.append(cat)
    return "> " + " · ".join(parts) if parts else ""


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


def _mermaid_safe_label(label: str, *, max_len: int = 28) -> str:
    s = re.sub(r'["\[\]#;|]', "", str(label or "")).strip()
    return (s[:max_len] or "topic").replace("\n", " ")


def format_weekly_best_rank_mermaid(
    label: str,
    rank_evidence_by_day: Dict[str, str],
) -> str:
    """週内の日別ベスト順位を Mermaid xychart で可視化。

    2日以上かつベスト順位に変化があるときのみ（同順の横ばいは表だけ）。
    プロット値を反転し上ほど上位。Y 軸数字は非表示（順位は点ラベルと表）。
    """
    points: List[tuple[str, int]] = []
    for ds, ev in sorted(rank_evidence_by_day.items()):
        best = _best_rank_from_evidence(ev)
        if best is not None:
            points.append((_short_calendar_date(ds), best))
    if len(points) < 2:
        return ""
    rank_vals = [r for _, r in points]
    if len(set(rank_vals)) < 2:
        return ""
    x_labels = [f"{d} ({r}位)" for d, r in points]
    title = _mermaid_safe_label(label)
    return sr.format_rank_mermaid_xychart(
        title,
        "順位の動き（上ほど上位）",
        x_labels,
        rank_vals,
    )


def _compact_weekly_link_line(item: Dict[str, Any]) -> str:
    """週次表示用: link_line から順位表記を除き、ソース名だけ残す。"""
    link = str(item.get("link_line") or "").strip()
    if not link:
        return str(item.get("label") or "")
    m = re.match(r"^(\[[^\]]+\]\([^)]+\))（([^·）]+)", link)
    if m:
        return f"{m.group(1)}（{m.group(2).strip()}）"
    return re.sub(r"（[^）]*）\s*$", "", link)


def render_weekly_rising_markdown(
    weekly_rising: Dict[str, List[Dict[str, Any]]],
) -> str:
    lines: List[str] = [_WEEKLY_RISING_HEADING, ""]
    any_items = False
    for region in WEEKLY_REGIONS:
        items = weekly_rising.get(region) or []
        lines.append(f"### {WEEKLY_REGION_LABELS[region]}")
        lines.append("")
        if not items:
            lines.append("（今週、順位が大きく動いた話題は見つかりませんでした）")
            lines.append("")
            continue
        any_items = True
        for i, it in enumerate(items, 1):
            link = _compact_weekly_link_line(it)
            lines.append(f"{i}. {link}")
            lines.append("")
            summary = format_weekly_rising_summary_line(it)
            if summary:
                lines.append(summary)
                lines.append("")
            rank_by_day = it.get("rank_evidence_by_day") or {}
            table = format_weekly_rank_table(rank_by_day)
            if table:
                lines.append(table)
                lines.append("")
            chart = format_weekly_best_rank_mermaid(str(it.get("label") or ""), rank_by_day)
            if chart:
                lines.append(chart)
                lines.append("")
    if not any_items:
        return (
            f"{_WEEKLY_RISING_HEADING}\n\n"
            "（今週、順位が大きく動いた話題は見つかりませんでした）\n"
        )
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
    flow_us = str(data.get("flow_us") or "").strip()
    if not flow_jp and not flow_us:
        raise ValueError("editorial JSON missing flow_jp / flow_us")

    carryover = data.get("carryover")
    if not isinstance(carryover, list):
        carryover = []
    carryover = [str(x).strip() for x in carryover if str(x).strip()]

    return {
        "flow_jp": flow_jp,
        "flow_us": flow_us,
        "carryover": carryover[:4],
    }


def assemble_weekly_markdown(
    iso_week: str,
    mon: date,
    sun: date,
    editorial: Dict[str, Any],
    weekly_rising: Dict[str, List[Dict[str, Any]]],
    weekly_cross: Dict[str, List[Dict[str, Any]]],
    meta: Dict[str, Any],
) -> str:
    lines: List[str] = [
        f"# 週次サマリー — {iso_week}（対象週 JST {mon.isoformat()}〜{sun.isoformat()}）",
        f"- **対象週**: {mon.isoformat()} 〜 {sun.isoformat()}",
        "- **生成・送信完了**: 自動生成（時刻未入力）",
        "",
        "## 今週の流れ（短文）",
        "",
        f"### {WEEKLY_REGION_LABELS['jp']}",
        "",
        (editorial.get("flow_jp") or "（日本向けの週次要約を生成できませんでした）").strip(),
        "",
        f"### {WEEKLY_REGION_LABELS['us']}",
        "",
        (editorial.get("flow_us") or "（アメリカ向けの週次要約を生成できませんでした）").strip(),
        "",
        "## 来週に残る論点（2〜4）",
        "",
    ]
    for item in editorial.get("carryover") or []:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(render_weekly_rising_markdown(weekly_rising).rstrip())
    lines.append("")
    lines.append(render_weekly_cross_markdown(weekly_cross).rstrip())
    premise = render_data_premise(meta)
    if premise:
        lines.append("")
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
) -> str:
    gen_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    range_s = f"{mon.isoformat()} 〜 {sun.isoformat()}"
    n_found = sum(1 for x in meta.get("daily_files", []) if x.get("found"))
    snap_found = meta.get("snapshot_days_found", 0)
    fm = f"""---
status: draft
iso_week: "{iso_week}"
week_range_jst: "{range_s}"
reviewer: ""
reviewed_at: ""
generator: openai
model: "{model}"
input_mode: "{meta.get('input_mode', 'snapshots')}"
snapshot_days_found: {snap_found}
snapshot_days_expected: 7
missing_snapshot_dates: {json.dumps(meta.get('missing_snapshot_dates') or [], ensure_ascii=False)}
partial_snapshot_dates: {json.dumps(meta.get('partial_snapshot_dates') or [], ensure_ascii=False)}
daily_files_found: {n_found}
daily_files_expected: 7
missing_daily_dates: {json.dumps(meta.get('missing_dates') or [], ensure_ascii=False)}
generated_at: "{gen_at}"
---

"""
    body = strip_wrapping_fences(inner_markdown)
    return fm + body


EDITORIAL_SYSTEM_PROMPT = """あなたはトレンドダッシュボードの週次サマリー編集者だ。
入力 JSON の weekly_mechanical.regions が事実の正本（JP/US 別のスナップショット週次集計）。
daily_summaries があれば補助。新しい URL・ラベル・事実を捏造しない。

このダッシュボードは **日本ページ** と **アメリカページ** の2地域を扱う。
週次サマリーも必ず両地域を対称に扱う（片方だけの要約は禁止）。

**出力は JSON オブジェクトのみ**（Markdown 不可）。キー:
- `flow_jp` (string): 3〜5文。日本向けソース（_jp / 日本語系列）の「今週の流れ」。
  weekly_mechanical.regions.jp のラベルを1件以上含める。米国話題だけの文は禁止。
- `flow_us` (string): 3〜5文。アメリカ向けソース（_us / 英語系列）の「今週の流れ」。
  weekly_mechanical.regions.us のラベルを1件以上含める。日本話題だけの文は禁止。
- `carryover` (array, 2〜4件): 来週に残る論点。日本・米国の両方から最低1件ずつ含める。
  各要素は「論点 — 1〜2文」。

禁止: 入力に無いラベル・URL・未来予測・Markdown 見出し。"""


LEGACY_SYSTEM_PROMPT = """あなたはトレンドダッシュボードの編集者だ。入力は、ある1週間（ISO 週・月曜始まり）
の各日について、すでにリポジトリに存在する「日次サマリー」Markdown の本文だけである。
各日の見出し日付（YYYY-MM-DD）は **その日のトレンド観測日（business_day）** であり、
ファイルが週のあとに生成されたこととは無関係に扱う。
新たに Web やトレンド API を参照したり、スナップショットを読んだりしない。

次を厳守すること:
- 出力は日本語の Markdown のみ（YAML フロントマターは書かない。先頭から # 見出しでよい）。
- 見出し構造:
  - `# 週次サマリー — ISO_WEEK（対象週 JST WEEK_MON〜WEEK_SUN）`
  - `- **対象週**:` と `- **生成・送信完了**:` の2行（生成時刻は「自動生成（時刻未入力）」でよい）
  - `## 今週の流れ（短文）`
  - `## 来週に残る論点（2〜4）`
- 「今週の流れ」は日次の繰り返しにせず、週としての要約にする。
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

    snap_meta, weekly_rising, weekly_cross = build_week_snapshot_rollups(
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

    mechanical = build_mechanical_llm_payload(weekly_rising, weekly_cross)
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
    raw = call_openai(EDITORIAL_SYSTEM_PROMPT, user, api_key, model, json_mode=True)
    editorial = parse_editorial_json(raw)
    warnings: List[str] = []
    for region in WEEKLY_REGIONS:
        if len(weekly_rising.get(region) or []) == 0:
            warnings.append(f"weekly_rising_{region} empty")
    if warnings:
        meta["editorial_warning"] = "; ".join(warnings)

    inner = assemble_weekly_markdown(
        stem, week_mon, week_sun, editorial, weekly_rising, weekly_cross, meta
    )
    meta["model"] = model
    full = merge_front_matter(stem, week_mon, week_sun, model, inner, meta)
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
    args = p.parse_args()

    if args.weekly_for_date:
        anchor = date.fromisoformat(args.weekly_for_date)
        week_mon, _ = week_range_mon_sun(anchor)
    else:
        week_mon = default_week_mon_jst()

    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)
    daily_dir = args.daily_dir if args.daily_dir is not None else DAILY_DIR

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

    if args.dry_run and not api_key:
        if args.daily_only:
            _, meta = build_daily_rollups(week_mon, week_sun, daily_dir)
            print(json.dumps(meta, ensure_ascii=False, indent=2))
        else:
            if via_http or database_url:
                try:
                    snap_meta, rising, cross = build_week_snapshot_rollups(
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

    if not api_key:
        print("❌ OPENAI_API_KEY（または OPEN_API_KEY）が未設定です", file=sys.stderr)
        return 1

    if args.daily_only:
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

    out = WEEKLY_DIR / f"{stem}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        print(f"skip (exists): {out.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 0

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
