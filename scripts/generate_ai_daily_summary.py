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
from urllib.parse import parse_qs, quote_plus, urlparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import snapshot_rising as sr

JST = ZoneInfo("Asia/Tokyo")
REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = REPO_ROOT / "docs" / "summaries" / "daily"
BASE_DEFAULT = "https://trends-dashboard.fly.dev"

SLOT_ORDER = ("07", "13", "19", "01")
# 一日の中での順位変化（07→13→19）。01 は締め用で jump には使わない。
DAYTIME_SLOTS = sr.DAYTIME_SLOTS
RISING_HIGHLIGHT_COUNT = 3
CROSS_SOURCE_HIGHLIGHT_COUNT = 3
CATEGORY_TOP_N = 3
_RISING_HEADING = "## 📈 昨日いちばん動いた3つ"
_CROSS_HEADING_PREFIX = "## 複数ソースで重なった話題"
_CROSS_NONE_LINE = (
    "該当なし（独立した取得元を2つ以上またいだ同一トピックはありませんでした）"
)
_TOP3_HEADING = "## 📊 カテゴリ別トップ3"
_TOP1_HEADING = "## 📊 カテゴリ別トップ1"
_NOTABLE_HEADING = "## 💡 昨日特異だったこと"
_ONE_LINER_HEADING = "## 今日の一行結論"
_SPOTLIGHTS_HEADING = "## 昨日の見どころ（3〜5）"
EDITORIAL_CANDIDATE_MAX = 12
SPOTLIGHT_MAX = 5
SPOTLIGHT_MIN = 2
_MECHANICAL_ONE_LINER_MAX = 420
_TEASER_MAX_CHARS = 90
_GENERIC_ONE_LINER = re.compile(
    r"(注目を集めて|人気です|が話題|盛り上がり|関心が高ま)",
    re.I,
)
_GENERIC_RISING_NOTE = re.compile(
    r"(若い世代|話題です|盛り上がり|関心が高ま|人気です|特に.*の間で|急上昇中|注目を集め)",
    re.I,
)
# 連日上位の定番（編集候補・一行結論から除外。トップ3根拠リストには残す）
_KNOWN_STALE_LABEL_KEYS = frozenset(
    {
        "build-your-own-x",
        "chatgpt",
        "ジハンピ",
        "canva（キャンバ） - 信じられないほど、素晴らしく",
        "canva",
    }
)
_KNOWN_STALE_LABEL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"windows\s*10.*サポート終了", re.I),
    re.compile(r"twig.*脆弱性", re.I),
    re.compile(r"31club|サーティワン公式アプリ", re.I),
)
# 一行結論の抽象語（後処理警告用）
_VAGUE_EDITORIAL_PHRASES = re.compile(
    r"(SNS投稿|定番アプリ|定番のGitHub|セキュリティ注意|App Storeの定番|"
    r"定番リポジトリ|いつも通り|各ソース)",
    re.I,
)
# 配信向けカテゴリ（行政はノイズが多いため digest から除外可）
CATEGORY_DIGEST_ORDER: tuple[str, ...] = (
    "ニュース",
    "検索・動画",
    "テック・開発",
    "マーケット",
    "エンタメ",
)
# クロスソースに使わない汎用カテゴリ名（「Sports」等は中身が分からない）
_GENERIC_CROSS_LABELS = frozenset(
    {
        "sports",
        "games",
        "gaming",
        "music",
        "news",
        "video",
        "videos",
        "entertainment",
        "business",
        "technology",
        "science",
        "politics",
        "movies",
        "anime",
        "manga",
        "books",
        "fashion",
        "travel",
        "food",
        "health",
        "finance",
        "crypto",
        "スポーツ",
        "ゲーム",
        "音楽",
        "ニュース",
        "動画",
        "エンタメ",
        "ビジネス",
        "テクノロジー",
        "科学",
        "政治",
        "映画",
        "アニメ",
        "本",
        "ファッション",
        "旅行",
        "グルメ",
    }
)
_PROVIDER_DISPLAY: Dict[str, str] = {
    "google_trends": "Google Trends",
    "youtube_trends": "YouTube",
    "wikipedia": "Wikipedia",
    "hatena": "はてな",
    "zenn": "Zenn",
    "qiita": "Qiita",
    "note": "note",
    "nhk": "NHK",
    "github": "GitHub",
    "twitch": "Twitch",
    "bluesky": "Bluesky",
    "prtimes": "PR TIMES",
    "prtimes_hatena": "PR TIMES × はてブ",
    "book_jp": "楽天ブックス",
    "book_us": "Google Books",
    "openalex": "OpenAlex",
    "worldnews": "World News",
    "cnn": "CNN",
    "rakuten": "楽天",
    "appstore": "App Store",
    "stock": "株価",
    "crypto": "暗号資産",
    "movie": "映画",
    "music_trends": "Spotify",
    "podcast": "Podcast",
    "jpcert": "JPCERT/CC",
    "ipa": "IPA",
    "cisa_kev": "CISA KEV",
    "thehackernews": "The Hacker News",
    "hackernoon": "Hacker Noon",
    "hackernews": "Hacker News",
    "producthunt": "Product Hunt",
    "devto": "DEV.to",
    "medium": "Medium",
    "ebay": "eBay",
    "globenewswire": "GlobeNewswire",
    "estat": "e-Stat",
    "kkj": "官公需",
    "bls": "BLS",
    "usaspending": "USAspending",
}
SLOT_LABELS = {
    "07": "7時台ジョブ後",
    "13": "13時台ジョブ後",
    "19": "19時台ジョブ後",
    "01": "翌1時台ジョブ後（前日を閉じる）",
}

# 読者向けスロット表記（DB の "07" 等をゼロ埋めせず 7時 / 7→13→19 にする）
DAYTIME_SLOTS_ARROW = "→".join(str(int(s)) for s in DAYTIME_SLOTS)


def _slot_hour_label(slot: str) -> str:
    try:
        return str(int(str(slot).strip()))
    except (ValueError, TypeError):
        s = str(slot or "").strip()
        return s.lstrip("0") or s or "0"

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
            entry: Dict[str, Any] = {"t": it.get("t"), "r": it.get("r")}
            u = it.get("u")
            if u and str(u).strip().startswith("http"):
                entry["u"] = str(u).strip()[:2000]
            thin.append(entry)
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


_snapshot_top_n = sr.snapshot_top_n
_rank_out_of_range = sr.rank_out_of_range
_normalize_label_key = sr.normalize_label_key
_clean_rising_display = sr.clean_rising_display
_is_weak_rising_label = sr.is_weak_rising_label
_rank_jump_score = sr.rank_jump_score
_rising_qualifies = sr.rising_qualifies
_daytime_best_rank = sr.daytime_best_rank
_pick_display_from_agg = sr.pick_display_from_agg
_is_noisy_label = sr.is_noisy_label


def _aggregate_labels_for_series(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
) -> Dict[str, Dict[str, Any]]:
    return sr.aggregate_labels_for_series(series_by_slot, series_key)


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


def series_region(series_key: str) -> Optional[str]:
    """スナップショット series_key の地域（jp / us）。曖昧な系列は None。"""
    sk = (series_key or "").strip().lower()
    if not sk:
        return None
    if sk.endswith("_jp") or "_jp_" in sk or sk.endswith("_ja"):
        return "jp"
    if sk.endswith("_us") or "_us_" in sk or sk.endswith("_en"):
        return "us"
    for prefix in (
        "nhk_",
        "prtimes",
        "rakuten_",
        "qiita_",
        "zenn_",
        "note_",
        "ipa_",
        "jpcert_",
        "hatena_",
        "estat_",
        "kkj_",
    ):
        if sk.startswith(prefix):
            return "jp"
    for prefix in (
        "cnn_",
        "hackernews_",
        "ebay_",
        "cisa_",
        "devto_",
        "thehackernews_",
        "producthunt_",
        "globenewswire",
        "bls_",
        "usaspending",
        "medium_",
    ):
        if sk.startswith(prefix):
            return "us"
    return None


def filter_rows_by_region(rows: List[Dict[str, Any]], region: str) -> List[Dict[str, Any]]:
    """series_key の地域が一致するスナップショット行だけ残す。"""
    want = (region or "").strip().lower()
    if want not in ("jp", "us"):
        return list(rows)
    out: List[Dict[str, Any]] = []
    for row in rows:
        sk = str(row.get("series_key") or "")
        if series_region(sk) == want:
            out.append(row)
    return out


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


def _is_generic_cross_source_label(display: str) -> bool:
    """ジャンル名だけのラベルはクロスソース候補から除外（中身が読めない）。"""
    s = _clean_rising_display(display)
    if not s:
        return True
    if _is_weak_rising_label(s):
        return True
    key = re.sub(r"\s+", " ", s).strip().lower()
    if key in _GENERIC_CROSS_LABELS:
        return True
    # 単語1つ・短い英字（Sports / Games 等の表記ゆれ）
    if re.fullmatch(r"[a-z][a-z0-9\s\-]{0,18}", key) and " " not in key.strip():
        return True
    return False


def _dedupe_series_keys_by_provider(series_keys: List[str]) -> List[str]:
    """同一プロバイダの地域別 series_key を1つにまとめる（表示・件数用）。"""
    by_prov: Dict[str, str] = {}
    for k in sorted(series_keys):
        p = _series_provider(k)
        prev = by_prov.get(p)
        if prev is None or _series_pref_score(k) > _series_pref_score(prev):
            by_prov[p] = k
    return sorted(by_prov.values())


def _format_series_key_display(series_key: str) -> str:
    """link_line 用: hatena_jp → はてな、wikipedia_ja → Wikipedia 等。"""
    sk = (series_key or "").strip()
    if not sk or sk == "?":
        return "?"
    if sk.startswith("prtimes_hatena"):
        name = _PROVIDER_DISPLAY["prtimes_hatena"]
    else:
        provider = _series_provider(sk)
        name = _PROVIDER_DISPLAY.get(provider) or provider.replace("_", " ")
    if sk.endswith("_us"):
        return f"{name} (US)"
    if sk.endswith("_en"):
        return f"{name} (EN)"
    return name


def _format_sources_display(series_keys: List[str]) -> str:
    """読者向けの取得元表示（twitch_jp + twitch_us → Twitch (US) のみ等）。"""
    return ", ".join(_format_series_key_display(k) for k in _dedupe_series_keys_by_provider(series_keys))


def _url_from_thin_item(item: Dict[str, Any]) -> Optional[str]:
    u = item.get("u")
    if u is None:
        return None
    s = str(u).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return None


def _normalize_article_url(url: str) -> Optional[str]:
    """記事同一性の比較用。Google 検索 URL など記事を指さないものは None。"""
    s = str(url or "").strip()
    if not s.startswith(("http://", "https://")):
        return None
    try:
        p = urlparse(s)
    except ValueError:
        return None
    host = (p.hostname or "").lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "/").rstrip("/") or "/"
    if host == "google.com" and path == "/search":
        return None
    if host in ("youtu.be",):
        vid = path.lstrip("/").split("/")[0]
        return f"youtube:{vid}" if vid else None
    if host in ("youtube.com", "m.youtube.com"):
        vid = (parse_qs(p.query).get("v") or [None])[0]
        return f"youtube:{vid}" if vid else None
    return f"{host}{path}".lower()


def _url_for_label_in_series(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
    label: str,
) -> Optional[str]:
    """系列内でラベルに対応する記事 URL（19→13→07→01 の順）。"""
    nk = _normalize_label_key(label)
    for slot in ("19", "13", "07", "01"):
        for it in (series_by_slot.get(slot) or {}).get(series_key) or []:
            if not isinstance(it, dict):
                continue
            if _normalize_label_key(str(it.get("t") or "")) == nk:
                u = _url_from_thin_item(it)
                if u:
                    return u
    return None


def _cross_source_is_same_article(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_keys: List[str],
    label: str,
) -> bool:
    """2系列以上で正規化 URL が一致 → 同一記事の再掲載とみなす。"""
    normalized: List[str] = []
    for sk in series_keys:
        u = _url_for_label_in_series(series_by_slot, sk, label)
        if not u:
            continue
        nu = _normalize_article_url(u)
        if nu:
            normalized.append(nu)
    if len(normalized) < 2:
        return False
    return len(set(normalized)) == 1


def _fallback_search_url(label: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(_clean_rising_display(label))}"


def _format_digest_link_line(
    label: str,
    series_key: str,
    rank_display: str,
    url: Optional[str] = None,
) -> str:
    """カテゴリ digest 用: リンク付き1行。"""
    href = url if url else _fallback_search_url(label)
    title = _clean_rising_display(label).replace("[", "\\[")
    source = _format_series_key_display(series_key)
    return f"[{title}]({href})（{source} · {rank_display}）"


def _format_slot_rank(slot: str, rank: int) -> str:
    return f"{_slot_hour_label(slot)}時{rank}位"


def _format_slot_rank_or_oob(slot: str, ranks: dict[str, int]) -> str:
    """top N に無いスロットは「圏外」。"""
    r = ranks.get(slot)
    if r is None:
        return f"{_slot_hour_label(slot)}時圏外"
    return _format_slot_rank(slot, int(r))


def _is_stale_label(display: str) -> bool:
    """連日上位の定番ラベル（編集価値が低い）。"""
    s = _clean_rising_display(display)
    if not s:
        return False
    nk = _normalize_label_key(s)
    if nk in _KNOWN_STALE_LABEL_KEYS:
        return True
    return any(p.search(s) for p in _KNOWN_STALE_LABEL_PATTERNS)


def _label_slot_coverage(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
    label: str,
) -> int:
    """07/13/19 のうち同一ラベルが観測されたスロット数。"""
    nk = _normalize_label_key(label)
    found: set[str] = set()
    for slot in DAYTIME_SLOTS:
        for it in (series_by_slot.get(slot) or {}).get(series_key) or []:
            if not isinstance(it, dict):
                continue
            if _normalize_label_key(str(it.get("t") or "")) == nk:
                found.add(slot)
    return len(found)


def _format_rank_evidence(ranks: dict[str, int]) -> str:
    """07→13→19 を常に3段表示（未掲載は圏外）。"""
    return " → ".join(_format_slot_rank_or_oob(slot, ranks) for slot in DAYTIME_SLOTS)


_RANK_EVIDENCE_SLOT_RE = re.compile(r"(\d+)時(?:(\d+)位|圏外)")


def _parse_rank_evidence(evidence: str) -> Dict[str, Optional[int]]:
    """rank_evidence 文字列を {07,13,19} → 順位（圏外は None）に分解。"""
    ranks: Dict[str, Optional[int]] = {slot: None for slot in DAYTIME_SLOTS}
    for m in _RANK_EVIDENCE_SLOT_RE.finditer(evidence or ""):
        slot = m.group(1).zfill(2)
        if slot not in ranks:
            continue
        rank_str = m.group(2)
        ranks[slot] = int(rank_str) if rank_str else None
    return ranks


def _ranks_dict_from_item(item: Dict[str, Any]) -> dict[str, int]:
    ranks = item.get("ranks")
    if isinstance(ranks, dict) and ranks:
        return {str(k): int(v) for k, v in ranks.items()}
    parsed = _parse_rank_evidence(str(item.get("rank_evidence") or ""))
    return {slot: int(r) for slot, r in parsed.items() if r is not None}


def _format_rank_cell(rank: Optional[int]) -> str:
    return "—" if rank is None else str(rank)


def format_daily_rank_table(ranks: dict[str, int]) -> str:
    """07/13/19 の順位を1行の Markdown 表にする。"""
    header = "| | 07 | 13 | 19 |"
    sep = "|:--:|:-:|:-:|:-:|"
    cells = [_format_rank_cell(ranks.get(slot)) for slot in DAYTIME_SLOTS]
    row = "| 順位 | " + " | ".join(cells) + " |"
    return "\n".join([header, sep, row])


def _mermaid_safe_label(label: str, *, max_len: int = 28) -> str:
    s = re.sub(r'["\[\]#;|]', "", str(label or "")).strip()
    return (s[:max_len] or "topic").replace("\n", " ")


def format_daily_slot_rank_mermaid(label: str, ranks: dict[str, int]) -> str:
    """一日のスロット別順位を Mermaid xychart で可視化。

    2スロット以上かつ順位に変化があるときのみ（同順の横ばいは表だけ）。
    """
    points: List[tuple[str, int]] = []
    for slot in DAYTIME_SLOTS:
        r = ranks.get(slot)
        if r is not None:
            points.append((f"{_slot_hour_label(slot)}時", int(r)))
    if len(points) < 2:
        return ""
    rank_vals = [r for _, r in points]
    if len(set(rank_vals)) < 2:
        return ""
    labels = ", ".join(f'"{h} ({r}位)"' for h, r in points)
    y_high = sr.mermaid_rank_y_axis_high(rank_vals)
    chart_values = ", ".join(str(r) for _, r in points)
    title = _mermaid_safe_label(label)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{title} — スロット別順位（上=1位）"\n'
        f"    x-axis [{labels}]\n"
        f'    y-axis "順位" {y_high} --> 1\n'
        f"    line [{chart_values}]\n"
        "```"
    )


def _compact_daily_link_line(item: Dict[str, Any]) -> str:
    """表示用: link_line から順位表記を除き、ソース名だけ残す。"""
    link = str(item.get("link_line") or "").strip()
    if not link:
        return str(item.get("label") or "")
    m = re.match(r"^(\[[^\]]+\]\([^)]+\))（([^·）]+)", link)
    if m:
        return f"{m.group(1)}（{m.group(2).strip()}）"
    return re.sub(r"（[^）]*）\s*$", "", link)


def format_daily_rising_summary_line(item: Dict[str, Any]) -> str:
    """1行サマリー（jump・区分）。"""
    parts: List[str] = []
    jump = item.get("jump")
    if jump is not None:
        parts.append(f"jump **+{jump}**")
    cat = (item.get("category") or "").strip()
    if cat:
        parts.append(cat)
    return "> " + " · ".join(parts) if parts else ""


def _daytime_label_sort_key(
    ranks: dict[str, int],
    *,
    jump: float = 0.0,
    coverage: int = 0,
    stale: bool = False,
    series_pref: int = 0,
) -> tuple:
    """一日評価: 定番除外 → 順位改善 → 複数スロット観測 → 最良順位 → 系列優先。"""
    return (
        1 if stale else 0,
        -jump,
        -coverage,
        _daytime_best_rank(ranks),
        -series_pref,
    )


def _merge_rank_maps(a: dict[str, int], b: dict[str, int]) -> dict[str, int]:
    out = dict(a)
    for slot, r in b.items():
        prev = out.get(slot)
        if prev is None or r < prev:
            out[slot] = r
    return out


def rows_to_series_by_slot(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """``{ slot: { series_key: items } }``（items は thin）。"""
    out: Dict[str, Dict[str, List[Dict[str, Any]]]] = {s: {} for s in SLOT_ORDER}
    for row in rows:
        slot, series_key, thin, _cap = _thin_items_from_row(row)
        if slot not in out or not thin:
            continue
        out[slot][series_key] = thin
    return out


def _url_for_rising_item(
    series_by_slot: Dict[str, Dict[str, List[Dict[str, Any]]]],
    series_key: str,
    label: str,
    ranks: dict[str, int],
) -> Optional[str]:
    nk = _normalize_label_key(label)
    for slot in ("19", "13", "07"):
        if slot not in ranks:
            continue
        for it in (series_by_slot.get(slot) or {}).get(series_key) or []:
            if not isinstance(it, dict):
                continue
            if _normalize_label_key(str(it.get("t") or "")) == nk:
                u = _url_from_thin_item(it)
                if u:
                    return u
    return None


def _rank_display_for_rising(ranks: dict[str, int]) -> str:
    """リンク行用: 07→13→19 の一日推移（単一スロットだけにしない）。"""
    return _format_rank_evidence(ranks)


def build_rising_highlights(
    rows: List[Dict[str, Any]],
    *,
    count: Optional[int] = RISING_HIGHLIGHT_COUNT,
) -> List[Dict[str, Any]]:
    """
    全 series 横断で 07→13→19 の順位改善が大きいラベルを返す。
    count 省略時は資格あり候補をすべて（週次集計用）。日次は count=3 等で上位のみ。
    """
    series_by_slot = rows_to_series_by_slot(rows)
    series_keys: set[str] = set()
    for slot in DAYTIME_SLOTS:
        series_keys |= set((series_by_slot.get(slot) or {}).keys())

    pool = sr.collect_rising_candidates(
        series_by_slot,
        sorted(series_keys),
    )
    if count is None:
        items = sorted(
            pool,
            key=lambda c: (-c["jump"], -c["freq"], c["r_best"], c["display"]),
        )
    else:
        items = sr.pick_top_rising(pool, count=count)
    out: List[Dict[str, Any]] = []
    for raw in items:
        ranks = dict(raw.get("ranks") or {})
        category = categorize_series_key(str(raw.get("series_key") or ""))
        picked = {
            "label": raw["display"],
            "category": category,
            "series_key": raw.get("series_key"),
            "jump": round(float(raw.get("jump") or 0), 1),
            "freq_slots": raw.get("freq"),
            "r_best": raw.get("r_best"),
            "ranks": ranks,
        }
        ranks = picked.pop("ranks", {})
        rank_evidence = _format_rank_evidence(ranks)
        rank_display = _rank_display_for_rising(ranks)
        url = _url_for_rising_item(series_by_slot, str(picked["series_key"]), str(picked["label"]), ranks)
        link_line = _format_digest_link_line(
            str(picked["label"]),
            str(picked["series_key"]),
            rank_display,
            url,
        )
        out.append(
            {
                **picked,
                "ranks": ranks,
                "rank_evidence": rank_evidence,
                "rank_display": rank_display,
                "url": url,
                "link_line": link_line,
            }
        )
    return out


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
            if (
                not display
                or _is_noisy_label(display, series_key)
                or _is_generic_cross_source_label(display)
            ):
                continue
            ranks = agg.get("ranks") or {}
            jump = _rank_jump_score(ranks)
            r_day_best = _daytime_best_rank(ranks)
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
                "best_daytime_rank": r_day_best,
                "series_pref": _series_pref_score(series_key),
            }
    return index


def build_cross_source_highlights(
    rows: List[Dict[str, Any]],
    *,
    count: Optional[int] = CROSS_SOURCE_HIGHLIGHT_COUNT,
) -> List[Dict[str, Any]]:
    """独立した取得元（_series_provider が2種以上）をまたいだ同一ラベル（正規化一致）を優先。

    タイトル一致でも URL が同一記事を指す場合は除外する（例: Zenn 記事のはてブ再掲載）。
    """
    index = _collect_label_index(rows)
    series_by_slot = rows_to_series_by_slot(rows)
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
        label = str(entry.get("label") or "")
        if _cross_source_is_same_article(series_by_slot, series_keys, label):
            continue
        deduped_keys = _dedupe_series_keys_by_provider(series_keys)
        jp_pref = max(s.get("series_pref", 0) for s in series_list)
        best_daytime_rank = min(
            (s.get("best_daytime_rank") or 999 for s in series_list),
            default=999,
        )
        max_jump = max(s.get("jump", 0.0) for s in series_list)
        candidates.append(
            {
                "label": entry["label"],
                "series_keys": deduped_keys,
                "sources_display": _format_sources_display(series_keys),
                "providers": sorted({_series_provider(k) for k in series_keys}),
                "categories": categories,
                "source_count": len(deduped_keys),
                "rank_evidence": series_list[0].get("rank_evidence", ""),
                "jump": max_jump,
                "best_daytime_rank": best_daytime_rank,
                "jp_series_pref": jp_pref,
            }
        )

    candidates.sort(
        key=lambda c: (
            -c["source_count"],
            -c["jp_series_pref"],
            c.get("best_daytime_rank") or 999,
            -c["jump"],
            c["label"],
        ),
    )
    if count is None:
        return candidates
    return candidates[:count]


def build_category_top3(
    rows: List[Dict[str, Any]],
    *,
    count: int = CATEGORY_TOP_N,
) -> List[Dict[str, Any]]:
    """カテゴリごとに 07/13/19 を横断した上位 N 件（順位改善・観測幅・最良順位）。"""
    series_by_slot = rows_to_series_by_slot(rows)
    all_series: set[str] = set()
    for slot in SLOT_ORDER:
        all_series |= set((series_by_slot.get(slot) or {}).keys())

    out: List[Dict[str, Any]] = []
    for category in CATEGORY_DIGEST_ORDER:
        cat_series = sorted(
            [sk for sk in all_series if categorize_series_key(sk) == category],
            key=lambda sk: (-_series_pref_score(sk), sk),
        )
        seen: set[str] = set()
        pool: List[Dict[str, Any]] = []
        for series_key in cat_series:
            aggs = _aggregate_labels_for_series(series_by_slot, series_key)
            for _nk, agg in aggs.items():
                ranks = agg.get("ranks") or {}
                if not ranks:
                    continue
                display = _pick_display_from_agg(agg)
                if _is_noisy_label(display, series_key):
                    continue
                jump = _rank_jump_score(ranks)
                coverage = len(set(ranks.keys()) & set(DAYTIME_SLOTS))
                stale = _is_stale_label(display)
                pool.append(
                    {
                        "label": display,
                        "series_key": series_key,
                        "url": _url_for_label_in_series(series_by_slot, series_key, display),
                        "rank_display": _format_rank_evidence(ranks),
                        "stale": stale,
                        "_sort": _daytime_label_sort_key(
                            ranks,
                            jump=jump,
                            coverage=coverage,
                            stale=stale,
                            series_pref=_series_pref_score(series_key),
                        ),
                    }
                )
        pool.sort(key=lambda x: x["_sort"])
        picked: List[Dict[str, Any]] = []
        for cand in pool:
            nk = _normalize_label_key(str(cand.get("label") or ""))
            if nk in seen:
                continue
            seen.add(nk)
            link_line = _format_digest_link_line(
                str(cand.get("label") or ""),
                str(cand.get("series_key") or ""),
                str(cand.get("rank_display") or ""),
                cand.get("url"),
            )
            picked.append(
                {
                    "label": cand["label"],
                    "series_key": cand["series_key"],
                    "rank_display": cand["rank_display"],
                    "url": cand.get("url"),
                    "link_line": link_line,
                }
            )
            if len(picked) >= count:
                break
        if picked:
            out.append({"category": category, "items": picked})
        else:
            out.append({"category": category, "items": [], "quiet": True})
    return out


def detect_quiet_editorial_categories(top3_blocks: List[Dict[str, Any]]) -> List[str]:
    """編集向けに「今日は静か」とみなす区分（トップ3がすべて定番など）。"""
    quiet: List[str] = []
    for block in top3_blocks:
        cat = str(block.get("category") or "")
        items = block.get("items") or []
        if block.get("quiet") or not items:
            quiet.append(cat)
            continue
        if all(_is_stale_label(str(it.get("label") or "")) for it in items):
            quiet.append(cat)
    return quiet


def quiet_category_examples(top3_blocks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """静かな区分向け: 定番ラベル例（一行結論で具体名を1つ出す用）。"""
    out: Dict[str, List[str]] = {}
    quiet = set(detect_quiet_editorial_categories(top3_blocks))
    for block in top3_blocks:
        cat = str(block.get("category") or "")
        if cat not in quiet:
            continue
        labels = [
            _clean_rising_display(str(it.get("label") or ""))
            for it in (block.get("items") or [])[:2]
            if str(it.get("label") or "").strip()
        ]
        if labels:
            out[cat] = labels
    return out


def build_editorial_candidates(
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    top3_blocks: List[Dict[str, Any]],
    rows: Optional[List[Dict[str, Any]]] = None,
    *,
    max_count: int = EDITORIAL_CANDIDATE_MAX,
) -> List[Dict[str, Any]]:
    """LLM 一行結論・見どころ用。定番除外・クロス/急上昇優先。"""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(
        label: str,
        *,
        category: str,
        series_key: str,
        reason: str,
        priority: int,
        rank_evidence: str = "",
        sources_display: str = "",
    ) -> None:
        display = _clean_rising_display(label)
        if not display or _is_noisy_label(display, series_key) or _is_stale_label(display):
            return
        nk = _normalize_label_key(display)
        if nk in seen:
            return
        seen.add(nk)
        out.append(
            {
                "label": display,
                "category": category,
                "series_key": series_key,
                "reason": reason,
                "priority": priority,
                "rank_evidence": rank_evidence,
                "sources_display": sources_display,
            }
        )

    for h in cross_items:
        series_keys = h.get("series_keys") or []
        sk = str(series_keys[0]) if series_keys else ""
        add(
            str(h.get("label") or ""),
            category="",
            series_key=sk,
            reason="cross_source",
            priority=0,
            rank_evidence=str(h.get("rank_evidence") or ""),
            sources_display=str(h.get("sources_display") or ""),
        )
    if rows:
        for leader in build_category_leaders_from_rows(rows):
            add(
                str(leader.get("label") or ""),
                category=str(leader.get("category") or ""),
                series_key=str(leader.get("series_key") or ""),
                reason="category_leader",
                priority=1,
                rank_evidence=str(leader.get("rank_display") or ""),
            )
    else:
        for block in top3_blocks:
            cat = str(block.get("category") or "")
            for it in block.get("items") or []:
                add(
                    str(it.get("label") or ""),
                    category=cat,
                    series_key=str(it.get("series_key") or ""),
                    reason="category_leader",
                    priority=1,
                    rank_evidence=str(it.get("rank_display") or ""),
                )
                break
    for r in rising_items:
        add(
            str(r.get("label") or ""),
            category=str(r.get("category") or ""),
            series_key=str(r.get("series_key") or ""),
            reason="rising",
            priority=2,
            rank_evidence=str(r.get("rank_evidence") or ""),
        )
    for block in top3_blocks:
        cat = str(block.get("category") or "")
        for it in block.get("items") or []:
            add(
                str(it.get("label") or ""),
                category=cat,
                series_key=str(it.get("series_key") or ""),
                reason="category_top",
                priority=3,
                rank_evidence=str(it.get("rank_display") or ""),
            )

    out.sort(
        key=lambda c: (
            c["priority"],
            c.get("rank_evidence") or "",
            c["label"],
        )
    )
    return out[:max_count]


def build_category_leaders_from_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """区分ごとに 07/13/19 を総合した代表1件（定番除外・順位改善・JP系列優先）。"""
    series_by_slot = rows_to_series_by_slot(rows)
    all_series: set[str] = set()
    for slot in SLOT_ORDER:
        all_series |= set((series_by_slot.get(slot) or {}).keys())

    leaders: List[Dict[str, Any]] = []
    for category in CATEGORY_DIGEST_ORDER:
        cat_series = sorted(
            [sk for sk in all_series if categorize_series_key(sk) == category],
            key=lambda sk: (-_series_pref_score(sk), sk),
        )
        best: Optional[Dict[str, Any]] = None
        for series_key in cat_series:
            aggs = _aggregate_labels_for_series(series_by_slot, series_key)
            for _nk, agg in aggs.items():
                ranks = agg.get("ranks") or {}
                display = _pick_display_from_agg(agg)
                if (
                    not display
                    or _is_noisy_label(display, series_key)
                    or _is_stale_label(display)
                ):
                    continue
                jump = _rank_jump_score(ranks)
                coverage = len(set(ranks.keys()) & set(DAYTIME_SLOTS))
                cand = {
                    "label": display,
                    "category": category,
                    "series_key": series_key,
                    "rank_display": _format_rank_evidence(ranks),
                    "url": _url_for_label_in_series(series_by_slot, series_key, display),
                    "_sort": _daytime_label_sort_key(
                        ranks,
                        jump=jump,
                        coverage=coverage,
                        series_pref=_series_pref_score(series_key),
                    ),
                }
                if best is None or cand["_sort"] < best["_sort"]:
                    best = cand
        if best:
            leaders.append({k: v for k, v in best.items() if k != "_sort"})
    return leaders


def build_label_link_index(
    rows: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    top3_blocks: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """正規化ラベル → リンク行・区分（spotlight の source_labels 解決用）。"""
    index: Dict[str, Dict[str, Any]] = {}
    series_by_slot = rows_to_series_by_slot(rows)

    def register(
        label: str,
        link_line: Optional[str],
        *,
        category: str = "",
        series_key: str = "",
    ) -> None:
        display = _clean_rising_display(label)
        if not display:
            return
        nk = _normalize_label_key(display)
        if nk in index:
            return
        href_line = link_line
        if not href_line:
            url = _url_for_label_in_series(series_by_slot, series_key, display) if series_key else None
            href_line = _format_digest_link_line(
                display,
                series_key or "?",
                DAYTIME_SLOTS_ARROW,
                url,
            )
        index[nk] = {
            "label": display,
            "link_line": href_line,
            "category": category,
            "series_key": series_key,
        }

    for r in rising_items:
        register(
            str(r.get("label") or ""),
            r.get("link_line"),
            category=str(r.get("category") or ""),
            series_key=str(r.get("series_key") or ""),
        )
    for block in top3_blocks:
        cat = str(block.get("category") or "")
        for it in block.get("items") or []:
            register(
                str(it.get("label") or ""),
                it.get("link_line"),
                category=cat,
                series_key=str(it.get("series_key") or ""),
            )
    for h in cross_items:
        label = str(h.get("label") or "")
        keys = h.get("series_keys") or []
        sk = str(keys[0]) if keys else ""
        url = _url_for_label_in_series(series_by_slot, sk, label) if sk else None
        line = _format_digest_link_line(label, sk or "?", DAYTIME_SLOTS_ARROW, url) if label else None
        register(label, line, series_key=sk)

    return index


def _resolve_source_labels(
    source_labels: List[Any],
    label_index: Dict[str, Dict[str, Any]],
) -> List[str]:
    """LLM の source_labels を link_line に解決（未知ラベルはスキップ）。"""
    lines: List[str] = []
    seen: set[str] = set()
    for raw in source_labels or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        nk = _normalize_label_key(raw)
        entry = label_index.get(nk)
        if entry is None:
            for key, ent in label_index.items():
                if nk in key or key in nk:
                    entry = ent
                    break
        if entry is None:
            continue
        line = str(entry.get("link_line") or entry.get("label") or "")
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def render_rising_highlights_markdown(
    items: List[Dict[str, Any]],
    rising_notes: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """昨日いちばん動いた3つ（07→13→19 の順位改善・機械生成 + AI 補足）。"""
    notes_by_label: Dict[str, str] = {}
    for n in rising_notes or []:
        if not isinstance(n, dict):
            continue
        ml = str(n.get("match_label") or "").strip()
        note = str(n.get("note") or "").strip()
        if ml and note:
            notes_by_label[_normalize_label_key(ml)] = note

    lines: List[str] = [_RISING_HEADING, ""]
    if not items:
        lines.append(
            f"（{DAYTIME_SLOTS_ARROW} の間で、順位が大きく上がった話題はありませんでした）"
        )
        return "\n".join(lines).rstrip() + "\n"
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {_compact_daily_link_line(it)}")
        lines.append("")
        summary = format_daily_rising_summary_line(it)
        if summary:
            lines.append(summary)
            lines.append("")
        label_nk = _normalize_label_key(str(it.get("label") or ""))
        note = notes_by_label.get(label_nk)
        if note:
            lines.append(f"   - **補足**: {note}")
            lines.append("")
        ranks = _ranks_dict_from_item(it)
        table = format_daily_rank_table(ranks)
        if table:
            lines.append(table)
            lines.append("")
        chart = format_daily_slot_rank_mermaid(str(it.get("label") or ""), ranks)
        if chart:
            lines.append(chart)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_cross_source_highlights_markdown(
    highlights: List[Dict[str, Any]],
    business_day: date,
    cross_intro: Optional[str] = None,
) -> str:
    """複数ソース重なり（機械生成・スナップショット事実 + 任意の AI 導入）。"""
    heading = f"{_CROSS_HEADING_PREFIX} — {business_day.isoformat()}"
    lines: List[str] = [heading, ""]
    if not highlights:
        lines.append(_CROSS_NONE_LINE)
        return "\n".join(lines).rstrip() + "\n"
    intro = (cross_intro or "").strip()
    if intro:
        lines.append(intro)
        lines.append("")
    for i, h in enumerate(highlights, 1):
        label = str(h.get("label") or "").strip() or "（ラベル不明）"
        lines.append(f"### {i}. {label}")
        lines.append("")
        lines.append("異なる取得元で同じ話題が観測されました。")
        sources = h.get("sources_display")
        if sources:
            lines.append(f"- **登場ソース**: {sources}")
        ranks = _ranks_dict_from_item(h)
        table = format_daily_rank_table(ranks)
        if table:
            lines.append("")
            lines.append(table)
        chart = format_daily_slot_rank_mermaid(str(h.get("label") or ""), ranks)
        if chart:
            lines.append("")
            lines.append(chart)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _section_end_after_heading(markdown: str, heading: str) -> Optional[int]:
    """見出し行の直後から次の `## ` 見出し（または文末）までの終端インデックス。"""
    idx = markdown.find(heading)
    if idx < 0:
        return None
    start = idx + len(heading)
    rest = markdown[start:]
    m = re.search(r"\n## ", rest)
    if m:
        return start + m.start()
    return len(markdown)


def _strip_cross_source_section(markdown: str) -> str:
    """LLM が書いた複数ソース見出しブロックを除去（日付付き見出し含む）。"""
    pattern = re.compile(
        rf"(?:\n|^){re.escape(_CROSS_HEADING_PREFIX)}[^\n]*\s*\n(?:.*?\n)*?(?=\n## |\Z)",
        re.DOTALL,
    )
    cleaned = pattern.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", cleaned.rstrip())


def inject_cross_source_highlights(markdown: str, cross_body: str) -> str:
    """急上昇の直後（なければメタ直後）に複数ソースブロックを1回だけ付与する。"""
    body = (cross_body or "").strip()
    if not body:
        return markdown
    cleaned = _strip_cross_source_section(markdown)
    rising_end = _section_end_after_heading(cleaned, _RISING_HEADING)
    if rising_end is not None:
        out = cleaned[:rising_end] + f"\n\n{body}\n" + cleaned[rising_end:].lstrip("\n")
    else:
        meta_re = re.compile(r"(- \*\*生成・送信完了\*\*:[^\n]*\n)")
        m2 = meta_re.search(cleaned)
        if m2:
            pos = m2.end()
            out = cleaned[:pos] + f"\n\n{body}\n" + cleaned[pos:].lstrip("\n")
        else:
            out = cleaned + f"\n\n{body}\n"
    if body.count(_CROSS_HEADING_PREFIX) != 1:
        raise RuntimeError(
            "inject_cross_source_highlights: expected exactly one cross-source heading"
        )
    return out


def render_category_top3_markdown(
    blocks: List[Dict[str, Any]],
    category_intros: Optional[Dict[str, str]] = None,
) -> str:
    """カテゴリ別トップ3の Markdown 本文（機械生成・リンク付き + 区分1文）。"""
    intros = category_intros or {}
    lines: List[str] = [_TOP3_HEADING, ""]
    for block in blocks:
        cat = block.get("category") or ""
        items = block.get("items") or []
        intro = (intros.get(cat) or "").strip() if isinstance(intros, dict) else ""
        if block.get("quiet") or not items:
            lines.append(f"- **{cat}**: （データなし）")
            continue
        lines.append(f"### {cat}")
        if intro:
            lines.append(f"**今日の傾向**: {intro}")
            lines.append("")
        for i, it in enumerate(items, 1):
            lines.append(f"{i}. {it.get('link_line') or it.get('label')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _category_has_items(cat_block: Dict[str, Any]) -> bool:
    for slot in cat_block.get("slots") or []:
        for ser in slot.get("series") or []:
            if ser.get("items"):
                return True
    return False


def _format_business_day_ja(business_day: date) -> str:
    return f"{business_day.year}年{business_day.month}月{business_day.day}日"


def render_header_markdown(business_day: date) -> str:
    bd = business_day.isoformat()
    ja = _format_business_day_ja(business_day)
    return "\n".join(
        [
            f"# 日次サマリー — {bd}（JST）",
            f"- **対象（観測日）**: {ja}",
            "- **生成・送信完了**: 自動生成（時刻未入力）",
        ]
    )


def render_editorial_markdown(
    editorial: Dict[str, Any],
    label_index: Dict[str, Dict[str, Any]],
) -> str:
    """一行結論のみ（急上昇は別セクションで表・図付き）。"""
    _ = label_index
    lines: List[str] = []
    one_liner = str(editorial.get("one_liner") or "").strip()
    if one_liner:
        lines.extend([_ONE_LINER_HEADING, "", one_liner, ""])
    return "\n".join(lines).rstrip()


def build_llm_payload(
    rows: List[Dict[str, Any]],
    business_day: date,
    *,
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    top3_blocks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """OpenAI 編集 JSON 用ペイロード（機械ファクト + 編集候補）。"""
    editorial_candidates = build_editorial_candidates(
        rising_items, cross_items, top3_blocks, rows
    )
    quiet_editorial = detect_quiet_editorial_categories(top3_blocks)
    return {
        "business_day": business_day.isoformat(),
        "reader_context": (
            "観測日（business_day）のトレンドを編集する。読者は通常翌朝に受け取る。"
            "「昨日」= business_day。未来予測は禁止。"
            "候補の rank_evidence は 07→13→19 の一日推移（圏外含む）。"
            "one_liner は rising_highlights の label を2件以上そのまま含め、"
            "ニュースの category_leader があればそれも含める（未達なら機械文に差し替えられる）。"
            "URL は出力しない。"
        ),
        "editorial_candidates": editorial_candidates,
        "quiet_editorial_categories": quiet_editorial,
        "quiet_category_examples": quiet_category_examples(top3_blocks),
        "rising_highlights": [
            {
                "label": r.get("label"),
                "category": r.get("category"),
                "rank_evidence": r.get("rank_evidence"),
            }
            for r in rising_items
        ],
        "cross_source_highlights": [
            {
                "label": h.get("label"),
                "sources_display": h.get("sources_display"),
                "rank_evidence": h.get("rank_evidence"),
            }
            for h in cross_items
        ],
    }


def build_user_payload(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > MAX_USER_CHARS:
        text = text[:MAX_USER_CHARS] + "\n…(truncated)"
    return text


def _clip_editorial_label(label: str, max_len: int = 48) -> str:
    s = _clean_rising_display(str(label or ""))
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _label_mentioned_in_text(label: str, text: str) -> bool:
    s = _clean_rising_display(label)
    if not s or not text:
        return False
    if s in text:
        return True
    nk = _normalize_label_key(s)
    tn = _normalize_label_key(text)
    if nk and nk in tn:
        return True
    probe = nk[: min(28, len(nk))]
    return len(probe) >= 10 and probe in tn


def one_liner_is_acceptable(
    one_liner: str,
    editorial_candidates: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
) -> bool:
    """LLM 一行が機械ファクトと整合しているか（自動配信用）。"""
    s = (one_liner or "").strip()
    if len(s) < 12 or len(s) > _MECHANICAL_ONE_LINER_MAX:
        return False
    if _warn_vague_one_liner(s) or _GENERIC_ONE_LINER.search(s):
        return False
    if rising_items:
        need = min(len(rising_items), 2)
        hits = sum(
            1
            for r in rising_items
            if _label_mentioned_in_text(str(r.get("label") or ""), s)
        )
        if hits < need:
            return False
    rising_nks = {_normalize_label_key(str(r.get("label") or "")) for r in rising_items}
    for c in editorial_candidates:
        if c.get("reason") != "category_leader" or c.get("category") != "ニュース":
            continue
        lab = str(c.get("label") or "")
        if _normalize_label_key(lab) in rising_nks:
            continue
        if not _label_mentioned_in_text(lab, s):
            return False
        break
    return True


def build_teaser_from_one_liner(one_liner: str, max_chars: int = _TEASER_MAX_CHARS) -> str:
    """Fake door 用: one_liner の先頭1文を短く切る。"""
    from services.summary.daily_summary_preview import clamp_teaser, first_sentence

    return clamp_teaser(first_sentence(one_liner), max_chars=max_chars)


def teaser_is_acceptable(
    teaser: str,
    rising_items: List[Dict[str, Any]],
) -> bool:
    s = (teaser or "").strip()
    if len(s) < 12 or len(s) > _TEASER_MAX_CHARS:
        return False
    if _warn_vague_one_liner(s) or _GENERIC_ONE_LINER.search(s):
        return False
    labels = [str(r.get("label") or "").strip() for r in rising_items if r.get("label")]
    if labels and not any(lab in s for lab in labels[:3]):
        return False
    return True


def build_mechanical_one_liner(
    editorial_candidates: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
) -> str:
    """データだけから組み立てる一行結論（LLM 不整合時のフォールバック）。"""
    sentences: List[str] = []

    if cross_items:
        lab = _clip_editorial_label(str(cross_items[0].get("label") or ""))
        ev = str(cross_items[0].get("rank_evidence") or "").strip()
        if lab:
            tail = f"（{ev}）" if ev else ""
            sentences.append(f"複数の取得元で「{lab}」が重なった{tail}。")

    news_leaders = [
        c
        for c in editorial_candidates
        if c.get("reason") == "category_leader" and c.get("category") == "ニュース"
    ]
    if news_leaders:
        c = news_leaders[0]
        lab = _clip_editorial_label(str(c.get("label") or ""))
        ev = str(c.get("rank_evidence") or "").strip()
        if lab:
            if ev:
                sentences.append(f"ニュースでは「{lab}」が一日を通して上位（{ev}）。")
            else:
                sentences.append(f"ニュースでは「{lab}」が一日を通して上位。")

    labels = [
        f"「{_clip_editorial_label(str(r.get('label') or ''))}」"
        for r in rising_items[:3]
        if str(r.get("label") or "").strip()
    ]
    if labels:
        if len(labels) == 1:
            sentences.append(f"順位の動きが大きかったのは{labels[0]}。")
        else:
            sentences.append(
                f"順位の動きが大きかったのは{'、'.join(labels[:-1])}と{labels[-1]}。"
            )

    if not sentences:
        return (
            f"{DAYTIME_SLOTS_ARROW} では、目立った順位の急上昇は限定的でした。"
            "カテゴリ別の上位は下記のとおりです。"
        )

    out = "".join(sentences)
    if len(out) > _MECHANICAL_ONE_LINER_MAX:
        out = out[: _MECHANICAL_ONE_LINER_MAX - 1].rstrip() + "…"
    return out


def _spotlight_will_render(
    sp: Dict[str, Any],
    label_index: Dict[str, Dict[str, Any]],
) -> bool:
    if not isinstance(sp, dict):
        return False
    title = str(sp.get("title") or "").strip()
    body = str(sp.get("body") or "").strip()
    if not title or not body:
        return False
    return bool(_resolve_source_labels(sp.get("source_labels") or [], label_index))


def build_mechanical_spotlight(
    *,
    label: str,
    rank_evidence: str = "",
    category: str = "",
) -> Dict[str, Any]:
    display = _clean_rising_display(label)
    title = _clip_editorial_label(display, max_len=40)
    ev = (rank_evidence or "").strip()
    if ev:
        body = f"{ev}。"
    elif category:
        body = f"{category}で上位に入った。"
    else:
        body = "順位が動いた。"
    return {
        "title": title or display[:40],
        "body": body,
        "source_labels": [display],
    }


def build_mechanical_spotlights(
    editorial_candidates: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    *,
    min_count: int = SPOTLIGHT_MIN,
    max_count: int = SPOTLIGHT_MAX,
) -> List[Dict[str, Any]]:
    """見どころが LLM で足りないときの機械生成（リンク解決可能なラベルのみ）。"""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def push(label: str, *, rank_evidence: str = "", category: str = "") -> None:
        if len(out) >= max_count:
            return
        display = _clean_rising_display(label)
        if not display:
            return
        nk = _normalize_label_key(display)
        if nk in seen:
            return
        seen.add(nk)
        out.append(
            build_mechanical_spotlight(
                label=display,
                rank_evidence=rank_evidence,
                category=category,
            )
        )

    for h in cross_items[:1]:
        push(
            str(h.get("label") or ""),
            rank_evidence=str(h.get("rank_evidence") or ""),
        )
    for r in rising_items:
        push(
            str(r.get("label") or ""),
            rank_evidence=str(r.get("rank_evidence") or ""),
            category=str(r.get("category") or ""),
        )
    for c in editorial_candidates:
        if c.get("reason") != "category_leader":
            continue
        push(
            str(c.get("label") or ""),
            rank_evidence=str(c.get("rank_evidence") or ""),
            category=str(c.get("category") or ""),
        )
        if len(out) >= min_count:
            break

    return out[:max_count]


def filter_rising_notes(
    notes: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """薄い定型補足を除き、必要なら根拠行ベースの機械補足に差し替える。"""
    allowed = {_normalize_label_key(str(r.get("label") or "")) for r in rising_items}
    out: List[Dict[str, Any]] = []
    for n in notes or []:
        if not isinstance(n, dict):
            continue
        ml = str(n.get("match_label") or "").strip()
        note = str(n.get("note") or "").strip()
        if not ml or not note or _GENERIC_RISING_NOTE.search(note):
            continue
        if _normalize_label_key(ml) not in allowed:
            continue
        out.append({"match_label": ml, "note": note})

    return out


def finalize_editorial(
    editorial: Dict[str, Any],
    *,
    editorial_candidates: List[Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    label_index: Dict[str, Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """LLM 編集 JSON を検証し、不足分は機械生成で補完（人手なし自動配信向け）。"""
    trace: Dict[str, Any] = {}
    mech_one = build_mechanical_one_liner(
        editorial_candidates, rising_items, cross_items
    )
    one = str(editorial.get("one_liner") or "").strip()
    if one_liner_is_acceptable(one, editorial_candidates, rising_items):
        trace["one_liner_source"] = "llm"
    else:
        editorial["one_liner"] = mech_one
        trace["one_liner_source"] = "mechanical"
        if one:
            trace["one_liner_replaced"] = True

    teaser = str(editorial.get("teaser") or "").strip()
    if teaser_is_acceptable(teaser, rising_items):
        trace["teaser_source"] = "llm"
    else:
        teaser = build_teaser_from_one_liner(str(editorial.get("one_liner") or ""))
        trace["teaser_source"] = "derived"
        if str(editorial.get("teaser") or "").strip():
            trace["teaser_replaced"] = True
    editorial["teaser"] = teaser

    editorial["spotlights"] = []
    editorial["rising_notes"] = filter_rising_notes(
        editorial.get("rising_notes") or [], rising_items
    )
    trace["spotlights_renderable"] = 0
    return editorial, trace


def call_openai(
    system: str,
    user: str,
    api_key: str,
    model: str,
    timeout: int = 120,
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


def parse_editorial_json(raw: str) -> Dict[str, Any]:
    """LLM 編集 JSON をパース・正規化。"""
    text = strip_wrapping_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"editorial JSON parse error: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError("editorial JSON must be an object")

    out: Dict[str, Any] = {
        "teaser": str(data.get("teaser") or "").strip(),
        "one_liner": str(data.get("one_liner") or "").strip(),
        "spotlights": [],
        "rising_notes": [],
        "cross_intro": data.get("cross_intro"),
        "category_intros": {},
    }
    if out["cross_intro"] is not None:
        out["cross_intro"] = str(out["cross_intro"]).strip() or None

    for sp in data.get("spotlights") or []:
        if isinstance(sp, dict):
            out["spotlights"].append(sp)
    out["spotlights"] = out["spotlights"][:SPOTLIGHT_MAX]

    for n in data.get("rising_notes") or []:
        if isinstance(n, dict) and n.get("match_label") and n.get("note"):
            out["rising_notes"].append(
                {
                    "match_label": str(n.get("match_label")),
                    "note": str(n.get("note")).strip(),
                }
            )

    ci = data.get("category_intros")
    if isinstance(ci, dict):
        for k, v in ci.items():
            if v and str(v).strip():
                out["category_intros"][str(k)] = str(v).strip()

    return out


def _warn_vague_one_liner(one_liner: str) -> Optional[str]:
    if not one_liner:
        return None
    if _VAGUE_EDITORIAL_PHRASES.search(one_liner):
        return "one_liner_contains_vague_phrase"
    return None


def assemble_daily_markdown(
    business_day: date,
    editorial: Dict[str, Any],
    label_index: Dict[str, Dict[str, Any]],
    rising_items: List[Dict[str, Any]],
    cross_items: List[Dict[str, Any]],
    top3_blocks: List[Dict[str, Any]],
) -> str:
    """ヘッダ + 編集 + 機械根拠セクションを合成。"""
    parts = [
        render_header_markdown(business_day),
        render_editorial_markdown(editorial, label_index),
        render_rising_highlights_markdown(rising_items, editorial.get("rising_notes")),
        render_cross_source_highlights_markdown(
            cross_items,
            business_day,
            editorial.get("cross_intro") if cross_items else None,
        ),
        render_category_top3_markdown(top3_blocks, editorial.get("category_intros")),
    ]
    return "\n\n".join(p.strip() for p in parts if p and p.strip()) + "\n"


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
    *,
    teaser: str = "",
) -> str:
    gen_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    teaser_line = ""
    if teaser:
        escaped = teaser.replace("\\", "\\\\").replace('"', '\\"')
        teaser_line = f'teaser: "{escaped}"\n'
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
{teaser_line}---

"""
    body = strip_wrapping_fences(inner_markdown)
    return fm + body


SYSTEM_PROMPT = """あなたはトレンドダッシュボードの編集者だ。入力 JSON の business_day は
**観測日**。読者は通常 **翌朝** に受け取る。「昨日」= business_day。

**出力は JSON オブジェクトのみ**（Markdown 不可）。次のキーを含める:

- `teaser` (string): **サイト無料プレビュー用**。1文・**最大90字**。主題は1つに絞る。
  rising_highlights の **先頭 label を1件**そのまま含める。順位の動きは括弧で短く（例: 7時圏外→19時1位）。
  2件目以降のトピックは書かない（それらは one_liner / 有料全文向け）。
- `one_liner` (string): 最大3文。必ず rising_highlights の label を **2件以上**そのまま含める。
  reason=category_leader かつ category=ニュース の候補が rising に無い場合は、その label も含める。
  「注目を集めて」「人気です」等の抽象表現は禁止。全カテゴリを無理に埋めない。
- `rising_notes` (array): `{ "match_label", "note" }` — rising_highlights の label に対応する1文補足。
  順位の事実の繰り返し・「急上昇中」「注目を集め」等の定型は禁止。rising_highlights が空なら []。
- `cross_intro` (string|null): cross_source_highlights が1件以上あるときのみ導入1〜2文。0件なら null。
- `category_intros` (object): キーは区分名、値は1文。quiet_editorial_categories 以外を優先。
  静かな区分は省略可。抽象語のみ（「定番アプリ」「SNS投稿」等）は禁止。

禁止:
- 入力 editorial_candidates / rising_highlights / cross_source_highlights に無いラベル・事実の捏造
- URL・Markdown 見出し
- 「〜でしょう」「今日は〜になる見込み」等の未来予測
- 「SNS投稿」「定番アプリ」「セキュリティ注意」等、具体ラベル無しの抽象カテゴリ語だけの記述
- cross_source_highlights が空なのに「複数ソースで重なった」と書くこと

事実: 入力に無いことは断定しない。"""

_MACHINE_DIGEST_HEADINGS = (
    _RISING_HEADING,
    _TOP1_HEADING,
    _TOP3_HEADING,
    _NOTABLE_HEADING,
)
_OLD_CROSS_HEADING = "## 昨日のクロスソースハイライト"


def _strip_machine_digest_sections(markdown: str) -> str:
    """LLM が書いた機械付与セクション（急上昇・トップ3・旧）を除去。"""
    cleaned = markdown
    for heading in _MACHINE_DIGEST_HEADINGS:
        pattern = re.compile(
            rf"(?:\n|^){re.escape(heading)}\s*\n(?:.*?\n)*?(?=\n## |\Z)",
            re.DOTALL,
        )
        cleaned = pattern.sub("", cleaned)
    old_cross = re.compile(
        rf"(?:\n|^){re.escape(_OLD_CROSS_HEADING)}[^\n]*\s*\n(?:.*?\n)*?(?=\n## |\Z)",
        re.DOTALL,
    )
    cleaned = old_cross.sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned.rstrip())


def inject_rising_highlights(markdown: str, rising_body: str) -> str:
    """ヘッダ直後（複数ソース見出しの前）に急上昇3つを1回だけ付与する。"""
    body = (rising_body or "").strip()
    if not body:
        return markdown
    cleaned = _strip_machine_digest_sections(markdown)
    cross_re = re.compile(
        rf"(\n)({re.escape(_CROSS_HEADING_PREFIX)}[^\n]*\n)",
    )
    m = cross_re.search(cleaned)
    if m:
        out = cleaned[: m.start(1)] + f"\n\n{body}\n" + cleaned[m.start(1) :]
    else:
        meta_re = re.compile(r"(- \*\*生成・送信完了\*\*:[^\n]*\n)")
        m2 = meta_re.search(cleaned)
        if m2:
            pos = m2.end()
            out = cleaned[:pos] + f"\n\n{body}\n" + cleaned[pos:].lstrip("\n")
        else:
            out = cleaned + f"\n\n{body}\n"
    if out.count(_RISING_HEADING) != 1:
        raise RuntimeError("inject_rising_highlights: expected exactly one rising heading")
    return out


def inject_category_top3(markdown: str, top3_body: str) -> str:
    """末尾にカテゴリ別トップ3を1回だけ付与する。"""
    body = (top3_body or "").strip()
    if not body:
        return markdown
    cleaned = _strip_machine_digest_sections(markdown)
    out = cleaned + f"\n\n{body}\n"
    if out.count(_TOP3_HEADING) != 1:
        raise RuntimeError("inject_category_top3: expected exactly one top3 heading")
    if _NOTABLE_HEADING in out:
        raise RuntimeError("inject_category_top3: notable heading must not remain")
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

    rising_items = build_rising_highlights(rows, count=RISING_HIGHLIGHT_COUNT)
    cross_items = build_cross_source_highlights(rows, count=CROSS_SOURCE_HIGHLIGHT_COUNT)
    top3_blocks = build_category_top3(rows, count=CATEGORY_TOP_N)
    label_index = build_label_link_index(rows, rising_items, cross_items, top3_blocks)

    payload = build_llm_payload(
        rows,
        business_day,
        rising_items=rising_items,
        cross_items=cross_items,
        top3_blocks=top3_blocks,
    )
    bd = business_day.isoformat()
    user = (
        f"business_day={bd}。観測日は {bd}。「昨日」= {bd}。\n\n"
        + build_user_payload(payload)
    )
    raw_editorial = call_openai(SYSTEM_PROMPT, user, api_key, model, json_mode=True)
    editorial = parse_editorial_json(raw_editorial)
    editorial, fin_trace = finalize_editorial(
        editorial,
        editorial_candidates=list(payload.get("editorial_candidates") or []),
        rising_items=rising_items,
        cross_items=cross_items,
        label_index=label_index,
    )
    vague_warn = _warn_vague_one_liner(str(editorial.get("one_liner") or ""))

    inner = assemble_daily_markdown(
        business_day,
        editorial,
        label_index,
        rising_items,
        cross_items,
        top3_blocks,
    )
    meta["model"] = model
    meta["rising_highlights_count"] = len(rising_items)
    meta["cross_source_highlights_count"] = len(cross_items)
    meta["editorial_candidates_count"] = len(payload.get("editorial_candidates") or [])
    meta["spotlights_count"] = len(editorial.get("spotlights") or [])
    meta["quiet_editorial_categories"] = payload.get("quiet_editorial_categories") or []
    meta.update(fin_trace)
    if vague_warn and meta.get("one_liner_source") == "llm":
        meta["editorial_warning"] = vague_warn
    full = merge_front_matter(
        business_day,
        model,
        inner,
        teaser=str(editorial.get("teaser") or ""),
    )
    return full, meta


def openai_api_key() -> str:
    """OPENAI_API_KEY を優先。ローカル .env の OPEN_API_KEY も受け付ける。"""
    return (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY") or "").strip()


def main() -> int:
    load_dotenv(_SCRIPT_DIR.parent / ".env")
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
    api_key = openai_api_key()
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

    if not rows:
        if via_http:
            snap_hint = (
                f"{base_url}/api/summaries/daily-snapshots"
                f"?business_day={bd.isoformat()}"
            )
            print(
                f"❌ business_day={bd} の trend_daily_snapshots 行がありません"
                f"（API 0 行: {snap_hint}）。",
                file=sys.stderr,
            )
            print(
                "   本番 DB に未保存・デプロイ直後・base URL 誤りの可能性。"
                " curl で行数を確認してから再実行してください。",
                file=sys.stderr,
            )
        else:
            print(
                f"❌ business_day={bd} の trend_daily_snapshots 行がありません（DB 0 行）。",
                file=sys.stderr,
            )
        emit_status(False, phase="snapshots", error="no_snapshot_rows", snapshot_row_count=0)
        return 2

    if args.dry_run and not api_key:
        rising_items = build_rising_highlights(rows, count=RISING_HIGHLIGHT_COUNT)
        cross_items = build_cross_source_highlights(rows, count=CROSS_SOURCE_HIGHLIGHT_COUNT)
        top3_blocks = build_category_top3(rows, count=CATEGORY_TOP_N)
        payload = build_llm_payload(
            rows,
            bd,
            rising_items=rising_items,
            cross_items=cross_items,
            top3_blocks=top3_blocks,
        )
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
