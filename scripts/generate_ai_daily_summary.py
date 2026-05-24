#!/usr/bin/env python3
"""
前日の business_day × スロット 07/13/19/01 の trend_daily_snapshots を読み、
OpenAI Chat Completions で日次サマリー Markdown を生成する。

スロット 01 は「翌暦日 1 時ジョブ」で前日を閉じるため、JST 朝 7 時の一括取得より前
（例: 6:50 JST）に走らせると前日分が揃った状態で取り込める。

  export DATABASE_URL=...
  export OPENAI_API_KEY=sk-...
  python scripts/generate_ai_daily_summary.py --dry-run
  python scripts/generate_ai_daily_summary.py --write --force

GitHub Actions 等 Fly 外では ``DATABASE_URL`` の ``*.flycast`` が解決できない。
リポジトリのワークフローでは ``--from-api`` を付ける。加えて、環境変数 ``GITHUB_ACTIONS=true``
かつ ``DATABASE_URL`` に Fly 内部 DNS（``.flycast`` / ``.internal``）が含まれる場合は、
``--from-api`` が無くても自動で HTTP スナップショット経路に切り替える（組織レベルで ``DATABASE_URL`` が
注入される場合の保険）。

  export OPENAI_API_KEY=sk-...
  python scripts/generate_ai_daily_summary.py --from-api --write --force

既定の対象日: JST の「昨日」（--business-day で上書き可）。
``--write`` 時の **``daily/{business_day}.md``** のファイル名は **観測日**（生成を実行した暦日ではない）。
例: 5/19 朝の GHA 実行 → ``2026-05-18.md``。詳細は ``docs/summaries/daily/README.md``。
HTTP モードのベース URL: ``TREND_DASHBOARD_BASE_URL``（既定 https://trends-dashboard.fly.dev）。

``--write`` 時、その ``business_day`` 向けに **``daily/YYYY-MM-DD.generation.json``** を必ず書く（成功 /
失敗 / キー欠如 / スナップショット空 / OpenAI 失敗）。CI でコミットするとリポジトリ上で結果が追える。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

JST = ZoneInfo("Asia/Tokyo")
REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = REPO_ROOT / "docs" / "summaries" / "daily"
BASE_DEFAULT = "https://trends-dashboard.fly.dev"

SLOT_ORDER = ("07", "13", "19", "01")
# 一日の中での順位変化（07→13→19）。01 は締め用で jump には使わない。
DAYTIME_SLOTS = ("07", "13", "19")
RISING_HIGHLIGHT_COUNT = 3
CROSS_SOURCE_HIGHLIGHT_COUNT = 3
# 配信向けカテゴリ別トップ1（行政はノイズが多いため digest から除外可）
CATEGORY_DIGEST_ORDER: tuple[str, ...] = (
    "ニュース",
    "検索・動画",
    "テック・開発",
    "マーケット",
    "エンタメ",
)
_WEAK_RISING_LABEL = re.compile(
    r"^(pickup|official|news|video|動画|ニュース|…+)$",
    re.I,
)
_NOISY_PROCUREMENT = re.compile(
    r"(LICENSE\s+RENEWAL|POP:\s*\d|INFINIBAND|FIBRE\s+OPTIC|usaspending|調達|契約番号)",
    re.I,
)
SLOT_LABELS = {
    "07": "07時台ジョブ後",
    "13": "13時台ジョブ後",
    "19": "19時台ジョブ後",
    "01": "翌1時台ジョブ後（前日を閉じる）",
}

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_USER_CHARS = 100_000

# 日次サマリーの論点見出し（この順・この文言で固定）
SUMMARY_CATEGORY_ORDER: tuple[str, ...] = (
    "ニュース",
    "検索・動画",
    "テック・開発",
    "マーケット",
    "エンタメ",
    "行政",
)
SUMMARY_CATEGORY_HINTS: dict[str, str] = {
    "ニュース": "NHK・ワールドニュース・CNN・プレス等",
    "検索・動画": "Google トレンド・YouTube・Wikipedia・SNS 等",
    "テック・開発": "Zenn・Qiita・GitHub・セキュリティ注意・HN 等",
    "マーケット": "株・暗号・楽天・App Store 等",
    "エンタメ": "音楽・映画・Podcast・書籍等",
    "行政": "e-Stat・官公需・米 BLS・政府支出等",
}


def write_generation_status(
    business_day: date,
    *,
    ok: bool,
    repo_root: Path = REPO_ROOT,
    daily_dir: Optional[Path] = None,
    **fields: Any,
) -> Path:
    """``daily/{business_day}.generation.json`` — Markdown の横に成否を残す（GHA でコミット用）。"""
    base = daily_dir if daily_dir is not None else repo_root / "docs" / "summaries" / "daily"
    base.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {
        "business_day": business_day.isoformat(),
        "ok": ok,
        "logged_at": datetime.now(JST).isoformat(),
        **fields,
    }
    path = base / f"{business_day.isoformat()}.generation.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def use_http_snapshots(*, cli_from_api: bool, database_url: str) -> bool:
    """True → ``fetch_snapshots_from_api``。GitHub Actions で Fly 専用 DB ホストが注入されたときのフォールバック。"""
    if cli_from_api:
        return True
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return False
    if not database_url:
        return False
    lo = database_url.lower()
    return ".flycast" in lo or ".internal" in lo


def default_business_day_jst(now: Optional[datetime] = None) -> date:
    """GHA / 手元で JST 朝に実行するときの既定: カレンダー上の昨日。"""
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    return now.date() - timedelta(days=1)


def fetch_snapshots(
    database_url: str, business_day: date, connect_timeout: int = 15
) -> List[Dict[str, Any]]:
    order_sql = " ".join(
        f"WHEN '{s}' THEN {i}" for i, s in enumerate(SLOT_ORDER)
    )
    sql = f"""
        SELECT slot, series_key, items, captured_at
        FROM trend_daily_snapshots
        WHERE business_day = %s AND slot IN ('01','07','13','19')
        ORDER BY CASE slot {order_sql} END, series_key
    """
    conn = psycopg2.connect(database_url, connect_timeout=connect_timeout)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (business_day,))
            return list(cur.fetchall())
    finally:
        conn.close()


def fetch_snapshots_from_api(
    base_url: str, business_day: date, timeout: int = 120
) -> List[Dict[str, Any]]:
    """本番 ``/api/summaries/daily-snapshots`` から DB と同形の行を取得する。"""
    url = (
        f"{base_url.rstrip('/')}/api/summaries/daily-snapshots"
        f"?business_day={business_day.isoformat()}"
    )
    r = requests.get(
        url,
        headers={"User-Agent": "trend-dashboard-ai-daily-summary/1.0"},
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
    return rows


def _thin_items_from_row(row: Dict[str, Any]) -> tuple[str, str, List[Dict[str, Any]], str]:
    """行から (slot, series_key, thin items) を取り出す。"""
    slot = str(row.get("slot") or "")
    series_key = str(row.get("series_key") or "")
    items = row.get("items")
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    if not isinstance(items, list):
        items = []
    thin: List[Dict[str, Any]] = []
    for it in items[:25]:
        if isinstance(it, dict) and it.get("t"):
            thin.append({"t": it.get("t"), "r": it.get("r")})
    cap = row.get("captured_at")
    cap_s = cap.isoformat() if hasattr(cap, "isoformat") else str(cap)
    return slot, series_key, thin, cap_s


def categorize_series_key(series_key: str) -> str:
    """snapshot の series_key を日次サマリー用カテゴリへ。"""
    sk = (series_key or "").strip().lower()
    if not sk:
        return "検索・動画"

    if sk in ("estat_jp", "kkj_jp", "bls_us", "usaspending_us"):
        return "行政"
    if sk.startswith("globenewswire_market"):
        return "マーケット"
    if any(
        sk.startswith(p)
        for p in (
            "nhk_",
            "worldnews_",
            "cnn_",
            "globenewswire",
            "prtimes",
        )
    ):
        return "ニュース"
    if any(
        sk.startswith(p)
        for p in (
            "stock_",
            "crypto_",
            "rakuten_",
            "ebay_",
            "appstore_",
        )
    ):
        return "マーケット"
    if any(
        sk.startswith(p)
        for p in (
            "music_",
            "movie_",
            "podcast_",
            "book_",
        )
    ):
        return "エンタメ"
    if any(
        sk.startswith(p)
        for p in (
            "zenn_",
            "qiita_",
            "github_",
            "jpcert_",
            "ipa_",
            "hackernews_",
            "devto_",
            "thehackernews_",
            "cisa_",
            "producthunt_",
            "medium_",
            "note_",
            "openalex_",
        )
    ):
        return "テック・開発"
    if any(
        sk.startswith(p)
        for p in (
            "google_trends_",
            "youtube_",
            "wikipedia_",
            "hatena_",
            "twitch_",
            "bluesky_",
        )
    ):
        return "検索・動画"

    return "テック・開発"


def compact_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 用に行をスロット単位でまとめる（レガシー形）。"""
    by_slot: Dict[str, List[Dict[str, Any]]] = {s: [] for s in SLOT_ORDER}
    for row in rows:
        slot, series_key, thin, cap_s = _thin_items_from_row(row)
        if slot not in by_slot:
            continue
        by_slot[slot].append(
            {
                "series_key": series_key,
                "captured_at": cap_s,
                "items": thin,
            }
        )
    return {
        "slots": [
            {
                "slot": s,
                "label_ja": SLOT_LABELS.get(s, s),
                "series": by_slot[s],
            }
            for s in SLOT_ORDER
        ],
    }


def compact_rows_by_category(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """LLM 用にカテゴリ → スロット → 系列でまとめる。"""
    # category -> slot -> list of series dicts
    buckets: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        cat: {s: [] for s in SLOT_ORDER} for cat in SUMMARY_CATEGORY_ORDER
    }
    for row in rows:
        slot, series_key, thin, cap_s = _thin_items_from_row(row)
        if slot not in SLOT_ORDER:
            continue
        cat = categorize_series_key(series_key)
        buckets[cat][slot].append(
            {
                "series_key": series_key,
                "captured_at": cap_s,
                "items": thin,
            }
        )
    categories = []
    for cat in SUMMARY_CATEGORY_ORDER:
        categories.append(
            {
                "category": cat,
                "hint": SUMMARY_CATEGORY_HINTS.get(cat, ""),
                "slots": [
                    {
                        "slot": s,
                        "label_ja": SLOT_LABELS.get(s, s),
                        "series": buckets[cat][s],
                    }
                    for s in SLOT_ORDER
                ],
            }
        )
    return {"categories": categories}


def _snapshot_top_n() -> int:
    try:
        return max(1, min(25, int(os.getenv("TREND_SNAPSHOT_TOP_N", "10"))))
    except (TypeError, ValueError):
        return 10


def _rank_out_of_range() -> int:
    return _snapshot_top_n() + 1


def _normalize_label_key(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).strip()).lower()[:600]


def _clean_rising_display(display: str) -> str:
    s = re.sub(r"^【[^】]{1,16}】\s*", "", str(display).strip())
    return re.sub(r"\s+", " ", s).strip()


def _is_weak_rising_label(display: str) -> bool:
    s = _clean_rising_display(display)
    if not s or s == "…" or len(s) < 4:
        return True
    return bool(_WEAK_RISING_LABEL.match(s))


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text)


def _series_pref_score(series_key: str) -> int:
    """JP 向け読者向け系列を優先（大きいほど良い）。"""
    sk = (series_key or "").lower()
    if sk.endswith("_jp") or "_jp_" in sk:
        return 3
    if sk.endswith("_us") or "_us_" in sk:
        return 0
    return 1


def _series_provider(series_key: str) -> str:
    """クロスソース判定用: 同一取得元（API・マネージャ・別カテゴリ/地域）を1プロバイダにまとめる。

    「複数ソース」は _series_provider が異なる系列同士のラベル一致のみ（完全に別の取得元同士）。
    """
    sk = (series_key or "").strip().lower()
    if not sk:
        return ""
    # 別カテゴリ・別ランキング軸の複数 series_key（同一マネージャ）
    if sk.startswith("openalex_"):
        return "openalex"
    if sk.startswith("globenewswire"):
        return "globenewswire"
    if sk.startswith("prtimes"):
        return "prtimes"
    if sk.startswith("book_jp_"):
        return "book_jp"
    if sk.startswith("book_us_"):
        return "book_us"
    # 標準形 {source}_{region} — 地域違いは同一プロバイダ
    for suffix in ("_jp", "_us", "_ja", "_en", "_global"):
        if sk.endswith(suffix):
            return sk[: -len(suffix)]
    return sk


def _format_slot_rank(slot: str, rank: int) -> str:
    return f"{slot}時スナップショット{rank}位"


def _is_noisy_label(display: str, series_key: str = "") -> bool:
    """調達行・英語長文など、一般読者向けサマリーから除外するラベル。"""
    if _is_weak_rising_label(display):
        return True
    s = _clean_rising_display(display)
    sk = (series_key or "").lower()
    if len(s) > 100:
        return True
    if _NOISY_PROCUREMENT.search(s):
        return True
    if any(p in sk for p in ("usaspending_", "kkj_", "estat_", "bls_")) and len(s) > 45:
        return True
    if _ascii_ratio(s) > 0.88 and len(s) > 50 and _series_pref_score(series_key) < 2:
        return True
    return False


def _format_rank_evidence(ranks: dict[str, int]) -> str:
    parts: List[str] = []
    for slot in DAYTIME_SLOTS:
        r = ranks.get(slot)
        if r is not None:
            parts.append(_format_slot_rank(slot, r))
    return " → ".join(parts) if parts else "順位データなし"


def _pick_display_from_agg(agg: Dict[str, Any]) -> str:
    by_slot = agg.get("display_by_slot") or {}
    for slot in ("19", "13", "07"):
        d = by_slot.get(slot)
        if d:
            return _clean_rising_display(str(d))
    return ""


def _merge_rank_maps(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out = dict(a)
    for slot, r in b.items():
        prev = out.get(slot)
        if prev is None or r < prev:
            out[slot] = r
    return out


def _rank_jump_score(ranks: dict[str, int]) -> float:
    oor = _rank_out_of_range()
    r7 = ranks.get("07")
    r13 = ranks.get("13")
    r19 = ranks.get("19")
    s = 0.0
    if r13 is not None:
        r7_eff = r7 if r7 is not None else oor
        s += max(0.0, float(r7_eff - r13))
    if r19 is not None:
        if r13 is not None:
            s += max(0.0, float(r13 - r19))
        elif r7 is None:
            s += max(0.0, float(oor - r19))
    if r7 is not None and r19 is not None and r13 is None:
        s += max(0.0, float(r7 - r19))
    return s


def rows_to_series_by_slot(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """``{ slot: { series_key: items } }``（items は thin）。"""
    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {s: {} for s in SLOT_ORDER}
    for row in rows:
        slot, series_key, thin, _cap = _thin_items_from_row(row)
        if slot not in out or not thin:
            continue
        out[slot][series_key] = thin
    return out


def _aggregate_labels_for_series(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for slot in DAYTIME_SLOTS:
        items = (series_by_slot.get(slot) or {}).get(series_key) or []
        for it in items:
            if not isinstance(it, dict):
                continue
            raw_t = it.get("t")
            if raw_t is None or not str(raw_t).strip():
                continue
            display = str(raw_t).strip()
            nk = _normalize_label_key(display)
            try:
                r = int(it.get("r"))
            except (TypeError, ValueError):
                r = 999
            agg = out.get(nk)
            if agg is None:
                agg = {"display_by_slot": {}, "ranks": {}, "series_key": series_key}
                out[nk] = agg
            agg["display_by_slot"][slot] = display
            prev = agg["ranks"].get(slot)
            if prev is None or r < prev:
                agg["ranks"][slot] = r
    return out


def build_rising_highlights(
    rows: List[Dict[str, Any]],
    *,
    count: int = RISING_HIGHLIGHT_COUNT,
) -> List[Dict[str, Any]]:
    """
    全 series 横断で 07→13→19 の順位改善が大きいラベルを最大 count 件。
    日次サマリーの「昨日いちばん動いた3つ」のたたき台。
    """
    series_by_slot = rows_to_series_by_slot(rows)
    series_keys: set[str] = set()
    for slot in DAYTIME_SLOTS:
        series_keys |= set((series_by_slot.get(slot) or {}).keys())

    best: Dict[str, Dict[str, Any]] = {}
    for series_key in series_keys:
        aggs = _aggregate_labels_for_series(series_by_slot, series_key)
        category = categorize_series_key(series_key)
        for nk, agg in aggs.items():
            ranks = agg.get("ranks") or {}
            jump = _rank_jump_score(ranks)
            display = _clean_rising_display(
                str((agg.get("display_by_slot") or {}).get("19")
                    or (agg.get("display_by_slot") or {}).get("13")
                    or (agg.get("display_by_slot") or {}).get("07")
                    or "")
            )
            if jump <= 0 or _is_noisy_label(display, series_key):
                continue
            freq = len(set(ranks.keys()) & set(DAYTIME_SLOTS))
            r_best = min(ranks.get(s, 999) for s in DAYTIME_SLOTS if s in ranks) if ranks else 999
            cand = {
                "label": display,
                "category": category,
                "series_key": series_key,
                "jump": round(jump, 1),
                "freq_slots": freq,
                "r_best": r_best,
                "best_rank_19": ranks.get("19"),
            }
            prev = best.get(nk)
            if prev is None or (cand["jump"], cand["freq_slots"], -cand["r_best"]) > (
                prev["jump"],
                prev["freq_slots"],
                -prev["r_best"],
            ):
                best[nk] = cand

    items = sorted(
        best.values(),
        key=lambda c: (-c["jump"], -c["freq_slots"], c.get("best_rank_19") or 999, c["label"]),
    )
    return items[:count]


def _collect_label_index(
    rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """正規化ラベル → 系列横断の集約（クロスソース検出用）。"""
    series_by_slot = rows_to_series_by_slot(rows)
    series_keys: set[str] = set()
    for slot in DAYTIME_SLOTS:
        series_keys |= set((series_by_slot.get(slot) or {}).keys())

    index: Dict[str, Dict[str, Any]] = {}
    for series_key in series_keys:
        aggs = _aggregate_labels_for_series(series_by_slot, series_key)
        category = categorize_series_key(series_key)
        for nk, agg in aggs.items():
            display = _pick_display_from_agg(agg)
            if not display or _is_noisy_label(display, series_key):
                continue
            ranks = agg.get("ranks") or {}
            jump = _rank_jump_score(ranks)
            r19 = ranks.get("19")
            entry = index.get(nk)
            if entry is None:
                entry = {
                    "label": display,
                    "series": {},
                }
                index[nk] = entry
            elif len(display) > len(str(entry.get("label") or "")):
                entry["label"] = display
            entry["series"][series_key] = {
                "series_key": series_key,
                "category": category,
                "ranks": ranks,
                "rank_evidence": _format_rank_evidence(ranks),
                "jump": round(jump, 1),
                "best_rank_19": r19,
                "series_pref": _series_pref_score(series_key),
            }
    return index


def build_cross_source_highlights(
    rows: List[Dict[str, Any]],
    *,
    count: int = CROSS_SOURCE_HIGHLIGHT_COUNT,
) -> List[Dict[str, Any]]:
    """独立した取得元（_series_provider が2種以上）をまたいだ同一ラベル（正規化一致）を優先。"""
    index = _collect_label_index(rows)
    candidates: List[Dict[str, Any]] = []
    for nk, entry in index.items():
        series_map = entry.get("series") or {}
        if len(series_map) < 2:
            continue
        series_list = list(series_map.values())
        categories = sorted({s["category"] for s in series_list})
        series_keys = sorted(series_map.keys())
        if len({_series_provider(k) for k in series_keys}) < 2:
            continue
        jp_pref = max(s.get("series_pref", 0) for s in series_list)
        best_r19 = min(
            (s.get("best_rank_19") or 999 for s in series_list),
            default=999,
        )
        max_jump = max(s.get("jump", 0.0) for s in series_list)
        candidates.append(
            {
                "label": entry["label"],
                "series_keys": series_keys,
                "categories": categories,
                "source_count": len(series_keys),
                "rank_evidence": series_list[0].get("rank_evidence", ""),
                "jump": max_jump,
                "best_rank_19": best_r19,
                "jp_series_pref": jp_pref,
            }
        )

    candidates.sort(
        key=lambda c: (
            -c["source_count"],
            -c["jp_series_pref"],
            c.get("best_rank_19") or 999,
            -c["jump"],
            c["label"],
        ),
    )
    return candidates[:count]


def _best_item_in_series_at_slot(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
    slot: str,
) -> Optional[Dict[str, Any]]:
    items = (series_by_slot.get(slot) or {}).get(series_key) or []
    best: Optional[Dict[str, Any]] = None
    for it in items:
        if not isinstance(it, dict) or not it.get("t"):
            continue
        try:
            r = int(it.get("r"))
        except (TypeError, ValueError):
            r = 999
        display = _clean_rising_display(str(it.get("t")))
        if _is_noisy_label(display, series_key):
            continue
        if best is None or r < best["rank"]:
            best = {"label": display, "rank": r, "slot": slot, "series_key": series_key}
    return best


def build_category_top1(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """カテゴリごとに 19→13→07 の最良1件（JP 系列優先）。"""
    series_by_slot = rows_to_series_by_slot(rows)
    all_series: set[str] = set()
    for slot in SLOT_ORDER:
        all_series |= set((series_by_slot.get(slot) or {}).keys())

    slot_weight = {"19": 3, "13": 2, "07": 1}
    out: List[Dict[str, Any]] = []
    for category in CATEGORY_DIGEST_ORDER:
        cat_series = sorted(
            [sk for sk in all_series if categorize_series_key(sk) == category],
            key=lambda sk: (-_series_pref_score(sk), sk),
        )
        picked: Optional[Dict[str, Any]] = None
        for series_key in cat_series:
            best_for_series: Optional[Dict[str, Any]] = None
            for slot in ("19", "13", "07"):
                cand = _best_item_in_series_at_slot(series_by_slot, series_key, slot)
                if cand is None:
                    continue
                score = (-cand["rank"], slot_weight.get(slot, 0))
                if best_for_series is None or score > best_for_series["_score"]:
                    best_for_series = {**cand, "_score": score}
            if best_for_series is None:
                continue
            full_score = (best_for_series["_score"], _series_pref_score(series_key))
            if picked is None or full_score > picked["_full_score"]:
                del best_for_series["_score"]
                picked = {**best_for_series, "category": category, "_full_score": full_score}
        if picked:
            del picked["_full_score"]
            picked["rank_display"] = _format_slot_rank(
                str(picked.get("slot") or ""),
                int(picked.get("rank") or 0),
            )
            out.append(picked)
        else:
            out.append({"category": category, "label": None, "quiet": True})
    return out


def _short_label(label: str, max_len: int = 32) -> str:
    s = _clean_rising_display(str(label or "")).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def build_notable_summary(
    cross_source: List[Dict[str, Any]],
    category_top1: List[Dict[str, Any]],
    quiet_categories: List[str],
) -> Dict[str, Any]:
    """「昨日特異だったこと」用: クロスソースと5区分トップ1の両方から推奨1文を組み立てる。"""
    cross_items: List[Dict[str, Any]] = []
    for c in cross_source[:CROSS_SOURCE_HIGHLIGHT_COUNT]:
        keys = list(c.get("series_keys") or [])
        cross_items.append(
            {
                "label": c.get("label"),
                "series_keys": keys,
                "rank_evidence": c.get("rank_evidence") or "",
            }
        )

    top1_items: List[Dict[str, Any]] = []
    for c in category_top1:
        if c.get("quiet") or not c.get("label"):
            continue
        top1_items.append(
            {
                "category": c.get("category"),
                "label": c.get("label"),
                "series_key": c.get("series_key"),
                "rank_display": c.get("rank_display") or "",
            }
        )

    hints: List[str] = []
    clauses: List[str] = []

    if cross_items:
        bits: List[str] = []
        for item in cross_items:
            label = _short_label(str(item.get("label") or ""))
            keys = item.get("series_keys") or []
            src = "・".join(keys[:3])
            if len(keys) > 3:
                src = f"{src} 他{len(keys) - 3}"
            bits.append(f"「{label}」（{src}）" if src else f"「{label}」")
        tail = f"{len(cross_items)}件" if len(cross_items) > 1 else "1件"
        clauses.append(f"複数ソースで重なったのは{'、'.join(bits)}の{tail}")
    else:
        clauses.append("異なるデータ源をまたいだ同一トピックの重複はなかった")

    if top1_items:
        top_bits = [
            f"{it['category']}「{_short_label(str(it.get('label') or ''))}」"
            for it in top1_items
        ]
        clauses.append(f"5区分の代表は{'、'.join(top_bits)}")
    elif quiet_categories:
        clauses.append(f"5区分はいずれもデータが薄い（{', '.join(quiet_categories[:3])}）")

    if len(top1_items) <= 2 and quiet_categories and top1_items:
        hints.append(f"動きが限定的（静か: {', '.join(quiet_categories[:3])}）")
    ent = next((c for c in category_top1 if c.get("category") == "エンタメ" and c.get("label")), None)
    search = next(
        (c for c in category_top1 if c.get("category") == "検索・動画" and c.get("label")), None
    )
    if ent and search and ent["label"] == search["label"]:
        hints.append("エンタメと検索・動画のトップ1が同一ラベル")

    recommended = "。".join(clauses) + "。"
    return {
        "cross_source_items": cross_items,
        "category_top1_items": top1_items,
        "recommended_sentence": recommended,
        "hints": hints,
    }


def build_notable_hints(
    cross_source: List[Dict[str, Any]],
    category_top1: List[Dict[str, Any]],
    quiet_categories: List[str],
) -> List[str]:
    """後方互換: notable_summary の hints リスト。"""
    return build_notable_summary(cross_source, category_top1, quiet_categories).get(
        "hints", []
    )


def _category_has_items(cat_block: Dict[str, Any]) -> bool:
    for slot in cat_block.get("slots") or []:
        for ser in slot.get("series") or []:
            if ser.get("items"):
                return True
    return False


def build_llm_payload(rows: List[Dict[str, Any]], business_day: date) -> Dict[str, Any]:
    """OpenAI 用: クロスソース・カテゴリ別トップ1・カテゴリ詳細。"""
    full = compact_rows_by_category(rows)
    categories = [c for c in full["categories"] if _category_has_items(c)]
    quiet = [c["category"] for c in full["categories"] if not _category_has_items(c)]
    cross = build_cross_source_highlights(rows, count=CROSS_SOURCE_HIGHLIGHT_COUNT)
    top1 = build_category_top1(rows)
    notable = build_notable_summary(cross, top1, quiet)
    rising = build_rising_highlights(rows, count=RISING_HIGHLIGHT_COUNT)
    return {
        "business_day": business_day.isoformat(),
        "reader_context": (
            "観測日（business_day）のトレンドをまとめる。読者は通常、観測日の翌朝に受け取る。"
            "「昨日」= business_day。推測や「今日は〜でしょう」は書かない。"
        ),
        "cross_source_highlights": cross,
        "category_top1": top1,
        "notable_summary": notable,
        "notable_hints": notable.get("hints", []),
        "rising_highlights_fallback": rising,
        "categories": categories,
        "quiet_categories": quiet,
    }


def build_user_payload(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > MAX_USER_CHARS:
        text = text[:MAX_USER_CHARS] + "\n…(truncated)"
    return text


def call_openai(
    system: str,
    user: str,
    api_key: str,
    model: str,
    timeout: int = 120,
) -> str:
    r = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.35,
            "max_tokens": 4096,
        },
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
    business_day: date,
    model: str,
    inner_markdown: str,
) -> str:
    gen_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    fm = f"""---
status: draft
summary_date: "{business_day.isoformat()}"
reviewer: ""
reviewed_at: ""
generator: openai
model: "{model}"
business_day: "{business_day.isoformat()}"
snapshot_slots_included: ["07", "13", "19", "01"]
generated_at: "{gen_at}"
---

"""
    body = strip_wrapping_fences(inner_markdown)
    return fm + body


SYSTEM_PROMPT = """あなたはトレンドダッシュボードの編集者だ。入力 JSON の business_day は
**観測日（その日のトレンド）**。読者は通常 **翌朝** に本文を受け取る。
Web 記事の本文や URL は含まれない。入力の cross_source_highlights / category_top1 /
notable_summary / categories はスナップショット由来の事実のみ。

出力は日本語 Markdown のみ（YAML フロントマターは書かない）。**BUSINESS_DAY** は JSON の
business_day と必ず一致させる。

構成（この順・見出し文言を厳守）:
1. `# 日次サマリー — BUSINESS_DAY（JST）`
2. `- **対象（観測日）**:` BUSINESS_DAY（例: 2026年5月20日）
3. `- **生成・送信完了**:`（不明なら「自動生成（時刻未入力）」）
4. `## 昨日のクロスソースハイライト — BUSINESS_DAY`
5. `### 🔥 複数ソースで話題になったもの` — **cross_source_highlights** を最大3件。
   0件なら「該当なし（独立した取得元を2つ以上またいだ同一トピックはありませんでした）」と1行だけ書き、
   rising_highlights_fallback から **JP 向けに読みやすい1件**を補足してもよい（根拠行必須）。
   各 `### 1.` …: 短い見出し（label）、本文2〜3文（**なぜ複数ソースに出たか**を推測しすぎず、
   ドラマ・事件・製品発表など **ありうる文脈**を「〜の可能性」と書く）、
   `- **登場ソース**:` series_keys をカンマ区切り、
   `- **根拠**:` rank_evidence または入力の rank_evidence をそのまま要約。
6. `## 📊 カテゴリ別トップ1` — **category_top1** の順（ニュース→検索・動画→テック→マーケット→エンタメ）。
   各行は `- **ニュース**:` のように **区分名だけ**（見出しの「カテゴリ」を繰り返さない。「カテゴリ名」という文字は書かない）。
   label（ソース: series_key · rank_display）。rank_display は入力のとおり（例: 19時スナップショット1位）。quiet なら「（データなし）」。

**「昨日特異だったこと」節は出力しない**（システムが末尾に機械生成文を1回だけ付与する）。
未来予測・「今日は〜」は禁止。

禁止:
- `## 今日の見方` / `## 昨日いちばん動いた3つ`（旧フォーマット）
- 「〜でしょう」「注目が集まる見込み」等の汎用予測
- 調達・英語長文タイトルの羅列をそのまま見出しにすること（入力にあっても要約・日本語化）
- 架空の URL
- 入力に無い事実の断定

事実: 入力に無いことは断定しない。クロスソースは「なぜ今」の手がかりとして最優先で説明する。"""

_NOTABLE_HEADING = "## 💡 昨日特異だったこと"


def inject_notable_sentence(markdown: str, sentence: str) -> str:
    """LLM 出力から「昨日特異」節をすべて除去し、機械生成の1文を末尾に1回だけ付与する。"""
    s = (sentence or "").strip()
    if not s:
        return markdown
    section_pattern = re.compile(
        rf"(?:\n|^){re.escape(_NOTABLE_HEADING)}\s*\n(?:.*?\n)*?(?=\n## |\Z)",
        re.DOTALL,
    )
    cleaned = section_pattern.sub("", markdown).rstrip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    out = cleaned + f"\n\n{_NOTABLE_HEADING}\n\n{s}\n"
    if out.count(_NOTABLE_HEADING) != 1:
        raise RuntimeError("inject_notable_sentence: expected exactly one notable heading")
    return out


def run_generate(
    business_day: date,
    rows: List[Dict[str, Any]],
    api_key: str,
    model: str,
) -> tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {
        "business_day": business_day.isoformat(),
        "row_count": len(rows),
    }
    if not rows:
        meta["error"] = "no_snapshot_rows"
        return "", meta

    payload = build_llm_payload(rows, business_day)
    bd = business_day.isoformat()
    user = (
        f"business_day={bd}。観測日は {bd}。「昨日」= {bd}。"
        f"見出し `# 日次サマリー — {bd}（JST）` と **対象（観測日）** も必ず {bd}。\n\n"
        + build_user_payload(payload)
    )
    inner = call_openai(SYSTEM_PROMPT, user, api_key, model)
    notable = payload.get("notable_summary") or {}
    recommended = notable.get("recommended_sentence")
    if recommended:
        inner = inject_notable_sentence(inner, str(recommended))
    meta["model"] = model
    meta["notable_recommended_sentence"] = recommended
    full = merge_front_matter(business_day, model, inner)
    return full, meta


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Generate daily AI summary from trend_daily_snapshots")
    p.add_argument(
        "--business-day",
        metavar="YYYY-MM-DD",
        help="Summarize this business_day (default: yesterday JST)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Without API key: print JSON payload only. With key: print full markdown to stdout",
    )
    p.add_argument(
        "--write",
        action="store_true",
        help="Write docs/summaries/daily/{business_day}.md and .generation.json (status)",
    )
    p.add_argument("--force", action="store_true", help="Overwrite existing file")
    p.add_argument(
        "--connect-timeout",
        type=int,
        default=20,
        help="DB connect timeout seconds",
    )
    p.add_argument(
        "--from-api",
        action="store_true",
        help="Fetch snapshots via TREND_DASHBOARD_BASE_URL (for CI / no DATABASE_URL). "
        "On GitHub Actions, also implied when DATABASE_URL uses .flycast / .internal.",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="Override TREND_DASHBOARD_BASE_URL for --from-api",
    )
    p.add_argument(
        "--request-timeout",
        type=int,
        default=120,
        help="HTTP timeout seconds for --from-api snapshot fetch",
    )
    args = p.parse_args()

    if args.business_day:
        bd = date.fromisoformat(args.business_day)
    else:
        bd = default_business_day_jst()

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_SUMMARY_MODEL") or "gpt-4o-mini").strip()
    base_url = (
        (args.base_url or os.getenv("TREND_DASHBOARD_BASE_URL") or BASE_DEFAULT).rstrip("/")
    )

    def emit_status(ok: bool, **fields: Any) -> None:
        """``--write`` かつ dry-run でないときだけ sidecar JSON を書く。"""
        if not args.write or args.dry_run:
            return
        p = write_generation_status(bd, ok=ok, **fields)
        print(f"wrote status {p.relative_to(REPO_ROOT)}", file=sys.stderr)

    via_http = use_http_snapshots(cli_from_api=args.from_api, database_url=database_url)
    if via_http and not args.from_api:
        print(
            "NOTE: GITHUB_ACTIONS with Fly-private DATABASE_URL; "
            "using /api/summaries/daily-snapshots (same as --from-api).",
            file=sys.stderr,
        )

    rows: List[Dict[str, Any]]

    if via_http:
        try:
            rows = fetch_snapshots_from_api(
                base_url, bd, timeout=args.request_timeout
            )
        except (requests.RequestException, json.JSONDecodeError, RuntimeError) as e:
            print(f"❌ スナップショット API 取得失敗: {e}", file=sys.stderr)
            emit_status(False, phase="snapshot_fetch", error=str(e))
            return 1
    else:
        if not database_url:
            print("❌ DATABASE_URL が未設定です（Fly 外の CI では --from-api を使う）", file=sys.stderr)
            emit_status(False, phase="config", error="missing_database_url_use_from_api")
            return 1
        try:
            rows = fetch_snapshots(
                database_url, bd, connect_timeout=args.connect_timeout
            )
        except psycopg2.Error as e:
            print(f"❌ DB スナップショット取得失敗: {e}", file=sys.stderr)
            emit_status(False, phase="snapshot_db", error=str(e))
            return 1

    if args.dry_run and not api_key:
        payload = build_llm_payload(rows, bd)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(
            f"\n# rows={len(rows)} (set OPENAI_API_KEY to generate summary text)",
            file=sys.stderr,
        )
        return 0

    if not api_key:
        print(
            "❌ OPENAI_API_KEY が未設定です（--dry-run のみ、キーなしでは JSON ペイロードを出せます）",
            file=sys.stderr,
        )
        emit_status(False, phase="config", error="missing_openai_api_key", snapshot_row_count=len(rows))
        return 1

    try:
        text, meta = run_generate(bd, rows, api_key, model)
    except RuntimeError as e:
        print(f"❌ OpenAI / 合成失敗: {e}", file=sys.stderr)
        emit_status(False, phase="openai", error=str(e), snapshot_row_count=len(rows))
        return 1

    if meta.get("error") == "no_snapshot_rows":
        print(
            f"❌ business_day={bd} の trend_daily_snapshots 行がありません。",
            file=sys.stderr,
        )
        emit_status(False, phase="snapshots", error="no_snapshot_rows", snapshot_row_count=0)
        return 2

    if args.dry_run:
        print(text)
        return 0

    if not args.write:
        print(text)
        return 0

    out = DAILY_DIR / f"{bd.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        print(f"skip (exists): {out.relative_to(REPO_ROOT)}", file=sys.stderr)
        emit_status(False, skipped=True, reason="markdown_exists_use_force", snapshot_row_count=len(rows))
        return 0

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    emit_status(
        True,
        markdown=str(out.relative_to(REPO_ROOT)),
        model=meta.get("model", model),
        snapshot_row_count=len(rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
