"""ダッシュボード号外帯: 現在版ラベル・次スロット・隣接スロット差分の注目3件。

カード全体の fresh ハイライトはしない。notable delta（新規入り / 大きな上昇）だけを返す。
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytz

from services.trend_snapshot_service import parse_scheduler_slot_key
from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = pytz.timezone("Asia/Tokyo")

# (calendar hour JST, scheduler name prefix, slot_code)
_SCHEDULE: Tuple[Tuple[int, str, str], ...] = (
    (1, "1am", "01"),
    (7, "7am", "07"),
    (13, "1pm", "13"),
    (19, "7pm", "19"),
)

SLOT_CODES = ("01", "07", "13", "19")
MAX_HIGHLIGHTS = 3
MIN_RANK_JUMP = 5
COMPARE_TOP_N = 10
JUST_REFRESHED_MINUTES = 45

_EXCLUDED_SERIES_PREFIXES: Tuple[str, ...] = (
    "medium_",
    "openalex_",
    "globenewswire",
    "ebay_",
    "bluesky_",
    "twitch_",
    "estat_",
    "kkj_",
    "bls_",
    "usaspending_",
)

_SOURCE_LABELS_JA: Dict[str, str] = {
    "google": "Google",
    "youtube": "YouTube",
    "wikipedia": "Wikipedia",
    "nhk": "NHK",
    "news": "News",
    "worldnews": "World News",
    "hatena": "はてブ",
    "qiita": "Qiita",
    "zenn": "Zenn",
    "note": "note",
    "github": "GitHub",
    "hackernews": "HN",
    "producthunt": "PH",
    "devto": "DEV.to",
    "cnn": "CNN",
    "music": "Music",
    "spotify": "Music",
    "podcast": "Podcast",
    "movie": "映画",
    "book": "本",
    "appstore": "App Store",
    "rakuten": "楽天",
    "crypto": "暗号資産",
    "stock": "株",
    "ipa": "IPA",
    "jpcert": "JPCERT",
    "cisakev": "CISA",
    "thehackernews": "THN",
    "prtimes_hatena": "PR×はてブ",
    "prtimes": "PR TIMES",
}

_SOURCE_LABELS_EN: Dict[str, str] = {
    "google": "Google",
    "youtube": "YouTube",
    "wikipedia": "Wikipedia",
    "nhk": "NHK",
    "news": "News",
    "worldnews": "World News",
    "hatena": "Hatena",
    "qiita": "Qiita",
    "zenn": "Zenn",
    "note": "note",
    "github": "GitHub",
    "hackernews": "HN",
    "producthunt": "PH",
    "devto": "DEV.to",
    "cnn": "CNN",
    "music": "Music",
    "spotify": "Music",
    "podcast": "Podcast",
    "movie": "Movies",
    "book": "Books",
    "appstore": "App Store",
    "rakuten": "Rakuten",
    "crypto": "Crypto",
    "stock": "Stocks",
    "ipa": "IPA",
    "jpcert": "JPCERT",
    "cisakev": "CISA",
    "thehackernews": "THN",
    "prtimes_hatena": "PR×Hatena",
    "prtimes": "PR TIMES",
}

_WS_RE = re.compile(r"\s+")


def _jst_at(d: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """JST の壁時計時刻。tzinfo=JST 直指定は LMT(+09:19) になるので localize 必須。"""
    return JST.localize(datetime(d.year, d.month, d.day, hour, minute, second))


def normalize_label_key(text: str) -> str:
    return _WS_RE.sub(" ", str(text or "").strip()).lower()[:600]


def series_matches_region(series_key: str, region: str) -> bool:
    sk = (series_key or "").strip().lower()
    want = (region or "jp").strip().lower()
    if not sk:
        return False
    if want == "us":
        return sk.endswith("_us") or "_us_" in sk or sk.endswith("_en")
    return sk.endswith("_jp") or "_jp_" in sk or sk.endswith("_ja")


def series_in_scope(series_key: str) -> bool:
    sk = (series_key or "").strip().lower()
    if not sk:
        return False
    if sk.startswith("prtimes") and not sk.startswith("prtimes_hatena"):
        return False
    return not any(sk.startswith(p) for p in _EXCLUDED_SERIES_PREFIXES)


def source_prefix(series_key: str) -> str:
    sk = (series_key or "").strip().lower()
    for suf in ("_jp", "_us", "_ja", "_en", "_global"):
        if sk.endswith(suf):
            sk = sk[: -len(suf)]
            break
    return sk


def source_label(series_key: str, locale: str = "ja") -> str:
    prefix = source_prefix(series_key)
    labels = _SOURCE_LABELS_EN if str(locale).lower().startswith("en") else _SOURCE_LABELS_JA
    if prefix in labels:
        return labels[prefix]
    if prefix.startswith("prtimes_hatena"):
        return labels.get("prtimes_hatena", prefix)
    return prefix or series_key


def data_source_attr(series_key: str) -> str:
    """全部入りカードの data-source に近いキー。"""
    prefix = source_prefix(series_key)
    aliases = {
        "worldnews": "news",
        "spotify": "music",
        "wikipedia": "wikipedia",
    }
    return aliases.get(prefix, prefix)


def previous_edition(business_day: date, slot_code: str) -> Tuple[date, str]:
    """同一サイクル上の直前スロット（07 の前は前日 business_day の 01）。"""
    code = str(slot_code).zfill(2)
    if code == "07":
        return business_day - timedelta(days=1), "01"
    if code == "13":
        return business_day, "07"
    if code == "19":
        return business_day, "13"
    if code == "01":
        return business_day, "19"
    raise ValueError(f"unsupported slot_code: {slot_code}")


def resolve_current_edition(
    now: Optional[datetime] = None,
) -> Tuple[datetime, date, str]:
    """直近の定時スロット開始時刻と (business_day, slot_code) を返す。"""
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = JST.localize(now)
    else:
        now = now.astimezone(JST)

    best: Optional[Tuple[datetime, date, str]] = None
    for day_offset in range(0, -4, -1):
        d = now.date() + timedelta(days=day_offset)
        for hour, name, _code in _SCHEDULE:
            start = _jst_at(d, hour)
            if start > now:
                continue
            parsed = parse_scheduler_slot_key(f"{name}_{d.isoformat()}")
            if not parsed:
                continue
            bd, slot = parsed
            if best is None or start > best[0]:
                best = (start, bd, slot)
    if best is None:
        # 理論上到達しないが安全側
        fallback_start = _jst_at(now.date() - timedelta(days=1), 19)
        return fallback_start, now.date() - timedelta(days=1), "19"
    return best


def resolve_next_refresh(now: Optional[datetime] = None) -> datetime:
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = JST.localize(now)
    else:
        now = now.astimezone(JST)

    for day_offset in range(0, 3):
        d = now.date() + timedelta(days=day_offset)
        for hour, _name, _code in _SCHEDULE:
            candidate = _jst_at(d, hour)
            if candidate > now:
                return candidate
    return now + timedelta(days=1)


def edition_label(slot_code: str, locale: str = "ja") -> str:
    code = str(slot_code).zfill(2)
    hour = int(code)
    if str(locale).lower().startswith("en"):
        return f"{hour:02d}:00 edition"
    return f"{hour}時版"


def is_just_refreshed(slot_start: datetime, now: Optional[datetime] = None) -> bool:
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = JST.localize(now)
    else:
        now = now.astimezone(JST)
    if slot_start.tzinfo is None:
        slot_start = JST.localize(slot_start)
    delta = now - slot_start.astimezone(JST)
    return timedelta(0) <= delta <= timedelta(minutes=JUST_REFRESHED_MINUTES)


def _parse_items(raw: Any) -> List[Dict[str, Any]]:
    items = raw
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in items[:COMPARE_TOP_N]:
        if not isinstance(it, dict):
            continue
        text = it.get("t")
        if text is None or not str(text).strip():
            continue
        rank = it.get("r")
        try:
            rank_i = int(rank) if rank is not None else len(out) + 1
        except (TypeError, ValueError):
            rank_i = len(out) + 1
        out.append({"t": str(text).strip(), "r": rank_i, "u": it.get("u")})
    return out


def _index_slot_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    slot_code: str,
    region: str,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """series_key → label_key → {display, rank, url}"""
    want = str(slot_code).zfill(2)
    by_series: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in rows:
        if str(row.get("slot") or "").zfill(2) != want:
            continue
        sk = str(row.get("series_key") or "")
        if not series_in_scope(sk) or not series_matches_region(sk, region):
            continue
        label_map: Dict[str, Dict[str, Any]] = {}
        for it in _parse_items(row.get("items")):
            key = normalize_label_key(it["t"])
            if not key or len(key) < 2:
                continue
            prev = label_map.get(key)
            if prev is None or it["r"] < int(prev["rank"]):
                label_map[key] = {
                    "display": it["t"][:120],
                    "rank": it["r"],
                    "url": it.get("u"),
                }
        if label_map:
            by_series[sk] = label_map
    return by_series


def build_highlights(
    current_rows: Sequence[Dict[str, Any]],
    previous_rows: Sequence[Dict[str, Any]],
    *,
    current_slot: str,
    previous_slot: str,
    region: str,
    locale: str = "ja",
    limit: int = MAX_HIGHLIGHTS,
) -> List[Dict[str, Any]]:
    """隣接スロット差分から注目を最大 limit 件。"""
    cur = _index_slot_rows(current_rows, slot_code=current_slot, region=region)
    prev = _index_slot_rows(previous_rows, slot_code=previous_slot, region=region)

    candidates: List[Dict[str, Any]] = []
    used_labels: set[str] = set()

    for sk, labels in cur.items():
        prev_labels = prev.get(sk) or {}
        for lk, cur_item in labels.items():
            if lk in used_labels:
                continue
            display = cur_item["display"]
            if len(display) < 2:
                continue
            prev_item = prev_labels.get(lk)
            kind: Optional[str] = None
            jump = 0
            rank_from: Optional[int] = None
            rank_to = int(cur_item["rank"])
            if prev_item is None:
                kind = "new"
                jump = COMPARE_TOP_N + 1 - rank_to
            else:
                rank_from = int(prev_item["rank"])
                jump = rank_from - rank_to
                if jump >= MIN_RANK_JUMP:
                    kind = "rising"
            if not kind:
                continue
            # NEW をやや優先、同種は jump / 上位寄せ
            score = (1000 if kind == "new" else 0) + jump * 10 + max(0, 20 - rank_to)
            candidates.append(
                {
                    "kind": kind,
                    "label": display,
                    "series_key": sk,
                    "source": source_label(sk, locale),
                    "data_source": data_source_attr(sk),
                    "rank_from": rank_from,
                    "rank_to": rank_to,
                    "jump": jump,
                    "url": cur_item.get("url"),
                    "score": score,
                    "_lk": lk,
                }
            )

    candidates.sort(key=lambda c: (-int(c["score"]), c["label"]))
    out: List[Dict[str, Any]] = []
    used_series: set[str] = set()
    for c in candidates:
        if len(out) >= limit:
            break
        sk = str(c["series_key"])
        lk = str(c.pop("_lk", ""))
        # 同一ソースは1件まで（多様性）
        if sk in used_series:
            continue
        if lk in used_labels:
            continue
        used_series.add(sk)
        used_labels.add(lk)
        c.pop("score", None)
        out.append(c)
    return out


def _load_slot_rows(cache: Any, business_day: date, slot_code: str) -> List[Dict[str, Any]]:
    if cache is None or not hasattr(cache, "get_trend_daily_snapshots_for_business_day"):
        return []
    try:
        rows = cache.get_trend_daily_snapshots_for_business_day(business_day) or []
    except Exception as e:
        logger.warning("edition_strip: snapshot load failed %s: %s", business_day, e)
        return []
    want = str(slot_code).zfill(2)
    return [r for r in rows if str(r.get("slot") or "").zfill(2) == want]


def build_edition_strip_payload(
    cache: Any,
    *,
    region: str = "jp",
    locale: str = "ja",
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """API / テンプレート用の号外ペイロード。"""
    if now is None:
        now = datetime.now(JST)
    slot_start, business_day, slot_code = resolve_current_edition(now)
    next_at = resolve_next_refresh(now)
    just = is_just_refreshed(slot_start, now)

    prev_bd, prev_slot = previous_edition(business_day, slot_code)
    current_rows = _load_slot_rows(cache, business_day, slot_code)
    previous_rows = _load_slot_rows(cache, prev_bd, prev_slot)
    highlights = build_highlights(
        current_rows,
        previous_rows,
        current_slot=slot_code,
        previous_slot=prev_slot,
        region=region,
        locale=locale,
    )

    loc = "en" if str(locale).lower().startswith("en") else "ja"
    return {
        "region": (region or "jp").strip().lower(),
        "locale": loc,
        "business_day": business_day.isoformat(),
        "slot": slot_code,
        "edition_label": edition_label(slot_code, loc),
        "slot_start": slot_start.isoformat(),
        "next_refresh_at": next_at.isoformat(),
        "just_refreshed": just,
        "highlights": highlights,
        "has_snapshot": bool(current_rows),
        "compare_slot": prev_slot,
        "compare_business_day": prev_bd.isoformat(),
    }
