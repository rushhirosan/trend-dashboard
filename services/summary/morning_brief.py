"""朝便り（カレンダー・マーケット・ひと息）を日次サマリー冒頭用 Markdown で組み立てる。"""

from __future__ import annotations

import json
import os
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from utils.logger_config import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
TOUNOU_RSS_URL = "https://meigen.tounou.net/?feed=rss2"
TOUNOU_ATTRIBUTION = "10秒名言"
TOUNOU_CATALOG_MAX_PAGES = 80
# 再生成で直近の格言がずれないよう、計画済みの行は少し残す
TOUNOU_ASSIGNMENT_KEEP_DAYS = 21
_POST_ID_RE = re.compile(r"[?&]p=(\d+)")

HTTP_HEADERS = {
    "User-Agent": (
        "TrendDashboardSummary/1.0 "
        "(https://trends-dashboard.com; summary-bot@trends-dashboard.com)"
    )
}

WIKI_UA = HTTP_HEADERS["User-Agent"]

JP_WEEKDAY_SHORT = ("月", "火", "水", "木", "金", "土", "日")
US_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

NAGER_COUNTRY = {"jp": "JP", "us": "US"}


@dataclass(frozen=True)
class MorningBriefLines:
    calendar: str
    alert: Optional[str] = None
    fx: Optional[str] = None
    stock: Optional[str] = None
    history: Optional[str] = None
    breath_second: Optional[str] = None


def delivery_day_for_business_day(business_day: date) -> date:
    """観測日の翌朝配信想定 → 読者の「今日」。"""
    return business_day + timedelta(days=1)


def _format_short_date(day: date, region: str) -> str:
    if (region or "jp").lower() == "us":
        wd = US_WEEKDAYS[day.weekday()]
        return f"{day.month}/{day.day} ({wd[:3]})"
    wd = JP_WEEKDAY_SHORT[day.weekday()]
    return f"{day.month}/{day.day}（{wd}）"


def _strip_wikitext(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<ref[^/>]*/>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\{\{[^}]+\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''|''", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _signed_delta(value: float, *, decimals: int = 1) -> str:
    fmt = f"{{:+.{decimals}f}}"
    return fmt.format(value)


def _signed_pct(value: float) -> str:
    return _signed_delta(value, decimals=1) + "%"


@lru_cache(maxsize=8)
def _fetch_public_holidays(year: int, country_code: str) -> tuple[Dict[str, str], ...]:
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        logger.warning("morning_brief: holidays fetch failed %s %s: %s", year, country_code, exc)
        return ()
    out: List[Dict[str, str]] = []
    for row in rows or []:
        d = str(row.get("date") or "").strip()
        if not d:
            continue
        name = str(row.get("localName") or row.get("name") or "").strip()
        if name:
            out.append({"date": d, "name": name})
    return tuple(out)


def _holiday_map_for_day(day: date, region: str) -> Dict[str, str]:
    country = NAGER_COUNTRY.get((region or "jp").lower(), "JP")
    merged: Dict[str, str] = {}
    for year in (day.year, day.year + 1):
        for row in _fetch_public_holidays(year, country):
            merged[row["date"]] = row["name"]
    return merged


def build_calendar_line(
    day: date,
    region: str,
    *,
    observation_day: Optional[date] = None,
) -> str:
    region_n = (region or "jp").lower()
    holidays = _holiday_map_for_day(day, region_n)
    iso = day.isoformat()
    parts: List[str] = [f"**{_format_short_date(day, region_n)}**"]
    if observation_day is not None:
        obs = f"{observation_day.month}/{observation_day.day}"
        if region_n == "us":
            parts.append(f"Brief date {obs}")
        else:
            parts.append(f"ブリーフ対象日 {obs}")
    if iso in holidays:
        name = holidays[iso]
        if region_n == "us":
            parts.append(f"Today: {name}")
        else:
            parts.append(f"{name}（祝日）")
        return " · ".join(parts)
    upcoming: List[tuple[date, str]] = []
    for ds, name in sorted(holidays.items()):
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        if d > day:
            upcoming.append((d, name))
    if upcoming:
        nd, name = upcoming[0]
        if region_n == "us":
            parts.append(f"Next holiday: {_format_short_date(nd, region_n)} {name}")
        else:
            parts.append(f"次の祝日は {_format_short_date(nd, region_n)}{name}")
    return " · ".join(parts)


def _fetch_yahoo_prior_close(ticker: str) -> Optional[tuple[float, float]]:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("morning_brief: yfinance not installed")
        return None
    try:
        hist = yf.Ticker(ticker).history(period="10d", auto_adjust=True)
    except Exception as exc:
        logger.warning("morning_brief: yfinance failed for %s: %s", ticker, exc)
        return None
    if hist is None or len(hist) < 2:
        return None
    closes = hist["Close"].dropna()
    if len(closes) < 2:
        return None
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    return last, prev


def build_market_lines(region: str) -> tuple[Optional[str], Optional[str]]:
    region_n = (region or "jp").lower()
    fx = _fetch_yahoo_prior_close("USDJPY=X")
    fx_line: Optional[str] = None
    if fx:
        last, prev = fx
        delta = last - prev
        if region_n == "us":
            fx_line = f"**FX** USD/JPY {last:.1f} ({_signed_delta(delta)} vs prior close)"
        else:
            fx_line = f"**為替** USD/JPY {last:.1f}（前日終値比 {_signed_delta(delta)}）"
    index_ticker = "^N225" if region_n == "jp" else "^GSPC"
    index_label = "日経" if region_n == "jp" else "S&P 500"
    idx = _fetch_yahoo_prior_close(index_ticker)
    stock_line: Optional[str] = None
    if idx:
        last, prev = idx
        if prev:
            pct = (last - prev) / prev * 100.0
        else:
            pct = 0.0
        if region_n == "us":
            stock_line = (
                f"**Stocks** {index_label} closed at {last:,.2f} ({_signed_pct(pct)})"
            )
        else:
            stock_line = (
                f"**株** {index_label} {last:,.0f}（前日終値 {_signed_pct(pct)}）"
            )
    return fx_line, stock_line


_US_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _format_history_year_en(year_val: Any) -> Optional[str]:
    try:
        year = int(year_val)
    except (TypeError, ValueError):
        return None
    if year < 0:
        return f"{abs(year)} BCE"
    if year == 0:
        return None
    return str(year)


def _format_en_on_this_day_line(
    day: date,
    text: str,
    year: Any = None,
) -> Optional[str]:
    """『この暦日・何年の出来事か』が本文だけだと分からないので両方出す。"""
    cleaned = _strip_wikitext(text)
    if not cleaned:
        return None
    year_s = _format_history_year_en(year)
    if year_s is None:
        year_match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", cleaned)
        if year_match:
            year_s = year_match.group(1)
            cleaned = cleaned[year_match.end() :].lstrip(" –—-,")
    else:
        cleaned = re.sub(
            rf"^(?:in\s+)?{re.escape(year_s)}\s*[,–—:-]\s*",
            "",
            cleaned,
            flags=re.I,
        )
    if not cleaned:
        return None
    month_day = f"{_US_MONTH_ABBR[day.month - 1]} {day.day}"
    when = f"{month_day}, {year_s}" if year_s else month_day
    return f"**On this day** {when} — {cleaned} (Wikipedia)"


def _split_jp_history_year(cleaned: str) -> Optional[tuple[str, str]]:
    """できごと行から年号と本文を分ける。紀元前は落とさない。"""
    year_match = re.search(r"(紀元前|前)?(\d{1,4})年", cleaned)
    if not year_match:
        return None
    era = "紀元前" if year_match.group(1) else ""
    year = f"{era}{year_match.group(2)}"
    rest = cleaned[year_match.end() :].lstrip("—－-・ ")
    rest = re.split(r"[（(]", rest, maxsplit=1)[0].strip(" 　—-")
    return year, rest


def _format_jp_history_line(day: date, year: str, rest: str) -> Optional[str]:
    event = str(rest or "").strip()
    if not event:
        return None
    return f"**歴史** {day.month}/{day.day} · {year}年 — {event}（Wikipedia）"


def _fetch_wikipedia_history_en(day: date) -> Optional[str]:
    mm = f"{day.month:02d}"
    dd = f"{day.day:02d}"
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{mm}/{dd}"
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": WIKI_UA})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("morning_brief: en onthisday failed: %s", exc)
        return None
    items = data.get("selected") or []
    if not items:
        return None
    item = items[0]
    return _format_en_on_this_day_line(
        day,
        str(item.get("text") or ""),
        year=item.get("year"),
    )


def _fetch_wikipedia_history_jp(day: date) -> Optional[str]:
    title = f"{day.month}月{day.day}日"
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "format": "json",
    }
    try:
        resp = requests.get(
            "https://ja.wikipedia.org/w/api.php",
            params=params,
            timeout=12,
            headers={"User-Agent": WIKI_UA},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("morning_brief: ja history fetch failed: %s", exc)
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    wikitext = ""
    for page in pages.values():
        revs = page.get("revisions") or []
        if not revs:
            continue
        wikitext = ((revs[0].get("slots") or {}).get("main") or {}).get("*") or ""
        break
    if not wikitext:
        return None
    in_events = False
    for line in wikitext.splitlines():
        if line.strip().startswith("==") and "できごと" in line:
            in_events = True
            continue
        if in_events and line.strip().startswith("=="):
            break
        if not in_events:
            continue
        if not line.strip().startswith("*"):
            continue
        cleaned = _strip_wikitext(line.lstrip("* ").strip())
        parsed = _split_jp_history_year(cleaned)
        if not parsed:
            continue
        year, rest = parsed
        formatted = _format_jp_history_line(day, year, rest)
        if formatted:
            return formatted
    return None


def build_history_line(day: date, region: str) -> Optional[str]:
    region_n = (region or "jp").lower()
    if region_n == "jp":
        line = _fetch_wikipedia_history_jp(day)
        if line:
            return line
    return _fetch_wikipedia_history_en(day)


_SKIP_TOUNOU_LINE_MARKERS = (
    "Facebook",
    "X で共有",
    "メルマガ",
    "続きを読む",
)


def _normalize_proverb_title(title: str) -> str:
    """RSS タイトルは名言全文。短いので切り詰めない。"""
    t = str(title or "").strip()
    if not t:
        return t
    if t.startswith("「"):
        return t
    return f"「{t}」"


_AUTHOR_REJECT_RE = re.compile(
    r"(実験|マウス|迷路|ため|です|である|について|における)|[でて]、?$|[。！？]$"
)


def _author_from_tounou_lines(lines: List[str]) -> Optional[str]:
    """本文先頭の『氏名（肩書…）』から発言者名だけ取る。"""
    if not lines:
        return None
    first = str(lines[0] or "").strip()
    if not first:
        return None
    match = re.match(r"^(.+?)\s*[（(]", first)
    name = (match.group(1) if match else first).strip()
    name = re.sub(r"\s+", " ", name)
    if len(name) < 2 or len(name) > 24:
        return None
    if _AUTHOR_REJECT_RE.search(name):
        return None
    if match is None and re.search(r"[をがには]、", name):
        return None
    return name


def _extract_tounou_article_lines(html: str) -> List[str]:
    match = re.search(
        r'class="entry-content[^"]*"[^>]*>(.*?)<!-- \.entry-content -->',
        html,
        re.S,
    )
    if not match:
        return []
    body = re.sub(r"<script[^>]*>.*?</script>", "", match.group(1), flags=re.S)
    body = re.sub(r"<[^>]+>", "\n", body)
    lines: List[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line == "»":
            continue
        if any(marker in line for marker in _SKIP_TOUNOU_LINE_MARKERS):
            continue
        lines.append(line)
    return lines


def _meaning_from_tounou_lines(lines: List[str]) -> Optional[str]:
    """著者行の次以降から、解説っぽい最初の段落を1つ取る。"""
    start = 1 if lines else 0
    for line in lines[start:]:
        if len(line) < 12:
            continue
        return line
    return None


def _proverb_cache_path() -> Path:
    """日次生成は GHA で DB を見ない。週の計画はこの JSON をコミットして持ち越す。"""
    override = os.getenv("TOUNOU_PROVERB_CACHE_PATH", "").strip()
    if override:
        return Path(override)
    return REPO_ROOT / "docs" / "summaries" / "tounou_proverb_cache.json"


def _tounou_post_id(item_el: ET.Element) -> str:
    for el in item_el.iter():
        if el.tag.endswith("post-id") and (el.text or "").strip().isdigit():
            return el.text.strip()
    blob = f"{item_el.findtext('link') or ''} {item_el.findtext('guid') or ''}"
    match = _POST_ID_RE.search(blob)
    return match.group(1) if match else ""


def _parse_tounou_rss_items(xml_text: str) -> List[Dict[str, str]]:
    if not str(xml_text or "").strip().startswith("<?xml"):
        return []
    root = ET.fromstring(xml_text)
    out: List[Dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        post_id = _tounou_post_id(item)
        if title and link and post_id:
            out.append({"id": post_id, "title": title, "link": link})
    return out


def _fetch_tounou_rss_page(page: int) -> List[Dict[str, str]]:
    url = TOUNOU_RSS_URL if page <= 1 else f"{TOUNOU_RSS_URL}&paged={page}"
    try:
        resp = requests.get(url, timeout=10, headers=HTTP_HEADERS)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("morning_brief: tounou RSS page %s failed: %s", page, exc)
        return []
    try:
        return _parse_tounou_rss_items(resp.text)
    except Exception as exc:
        logger.warning("morning_brief: tounou RSS page %s parse failed: %s", page, exc)
        return []


def _fetch_tounou_catalog() -> List[Dict[str, str]]:
    """RSS を最終ページまで辿る。1ページは10件なので、先頭だけでは週次で同じ格言に戻る。"""
    catalog: List[Dict[str, str]] = []
    seen: set[str] = set()
    for page in range(1, TOUNOU_CATALOG_MAX_PAGES + 1):
        items = _fetch_tounou_rss_page(page)
        if not items:
            break
        fresh = [item for item in items if item["id"] not in seen]
        if not fresh:
            break
        for item in fresh:
            seen.add(item["id"])
            catalog.append(item)
    catalog.sort(key=lambda item: int(item["id"]))
    return catalog


def _fetch_tounou_rss_items(*, max_items: int = 30) -> List[Dict[str, str]]:
    """キャッシュが空のときの先頭ページだけ。"""
    return _fetch_tounou_rss_page(1)[:max_items]


def _fetch_tounou_speaker(article_url: str) -> Optional[str]:
    try:
        resp = requests.get(article_url, timeout=12, headers=HTTP_HEADERS)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("morning_brief: tounou article fetch failed: %s", exc)
        return None
    lines = _extract_tounou_article_lines(resp.text)
    return _author_from_tounou_lines(lines)


def _select_tounou_item_for_day(items: List[Dict[str, str]], day: date) -> Optional[Dict[str, str]]:
    if not items:
        return None
    idx = day.toordinal() % len(items)
    return items[idx]


def _week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _empty_proverb_cache() -> Dict[str, Any]:
    return {
        "week_start": "",
        "fetched_at": "",
        "pending_ids": [],
        "catalog": [],
        "assignments": {},
    }


def _load_proverb_cache() -> Dict[str, Any]:
    path = _proverb_cache_path()
    if not path.is_file():
        return _empty_proverb_cache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("morning_brief: proverb cache unreadable: %s", exc)
        return _empty_proverb_cache()
    if not isinstance(data, dict):
        return _empty_proverb_cache()
    data.setdefault("week_start", "")
    data.setdefault("fetched_at", "")
    data.setdefault("pending_ids", [])
    data.setdefault("catalog", [])
    data.setdefault("assignments", {})
    return data


def _save_proverb_cache(cache: Dict[str, Any]) -> None:
    path = _proverb_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cache, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _merge_proverb_catalog(
    old_catalog: List[Dict[str, str]],
    pending_ids: List[str],
    fresh: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[str]]:
    """新着 ID は未出キューの先頭へ。既存の並びは崩さない。"""
    old_ids = {str(item.get("id") or "") for item in old_catalog}
    pending_set = {str(pid) for pid in pending_ids}
    catalog: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in fresh:
        post_id = str(item.get("id") or "")
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        catalog.append({"id": post_id, "title": item.get("title") or "", "link": item.get("link") or ""})
    catalog.sort(key=lambda item: int(item["id"]))
    newcomers = [
        item["id"]
        for item in catalog
        if item["id"] not in old_ids and item["id"] not in pending_set
    ]
    newcomers.sort(key=lambda post_id: int(post_id), reverse=True)
    pending = newcomers + [str(pid) for pid in pending_ids if str(pid) in seen]
    return catalog, pending


def _prune_assignments(assignments: Dict[str, str], monday: date) -> Dict[str, str]:
    cutoff = monday - timedelta(days=TOUNOU_ASSIGNMENT_KEEP_DAYS)
    kept: Dict[str, str] = {}
    for key, line in assignments.items():
        try:
            assigned = date.fromisoformat(str(key))
        except ValueError:
            continue
        if assigned >= cutoff and line:
            kept[str(key)] = str(line)
    return kept


def _assign_proverb_week(
    catalog: List[Dict[str, str]],
    pending_ids: List[str],
    monday: date,
) -> Tuple[Dict[str, str], List[str]]:
    """週の7日を埋める。未出があれば月曜から順に使い、足りなければ一覧から補う。"""
    by_id = {item["id"]: item for item in catalog if item.get("id")}
    pending = [pid for pid in pending_ids if pid in by_id]
    rng = random.Random(monday.toordinal())
    pool_ids = [item["id"] for item in catalog]
    rng.shuffle(pool_ids)
    pool_at = 0
    used: set[str] = set()
    assignments: Dict[str, str] = {}
    for offset in range(7):
        day = monday + timedelta(days=offset)
        chosen: Optional[str] = None
        while pending:
            pid = pending.pop(0)
            if pid not in used and pid in by_id:
                chosen = pid
                break
        if chosen is None:
            while pool_at < len(pool_ids):
                pid = pool_ids[pool_at]
                pool_at += 1
                if pid not in used:
                    chosen = pid
                    break
        if chosen is None and catalog:
            chosen = catalog[day.toordinal() % len(catalog)]["id"]
        if not chosen or chosen not in by_id:
            continue
        used.add(chosen)
        item = by_id[chosen]
        author = _fetch_tounou_speaker(item["link"])
        assignments[day.isoformat()] = _format_jp_proverb_line(item["title"], author=author)
    return assignments, pending


def _fallback_proverb_line(catalog: List[Dict[str, str]], day: date) -> Optional[str]:
    item = _select_tounou_item_for_day(catalog, day)
    if not item:
        return None
    author = _fetch_tounou_speaker(item.get("link") or "")
    return _format_jp_proverb_line(item.get("title") or "", author=author)


def _legacy_proverb_line(day: date) -> Optional[str]:
    items = _fetch_tounou_rss_items()
    item = _select_tounou_item_for_day(items, day)
    if not item:
        return None
    author = _fetch_tounou_speaker(item["link"])
    return _format_jp_proverb_line(item["title"], author=author)


def _proverb_line_for_day(day: date) -> Optional[str]:
    cache = _load_proverb_cache()
    assignments = cache.get("assignments") or {}
    cached_line = assignments.get(day.isoformat())
    if cached_line:
        return str(cached_line)

    monday = _week_monday(day)
    week_start_raw = str(cache.get("week_start") or "")
    if week_start_raw:
        try:
            stored_monday = date.fromisoformat(week_start_raw)
        except ValueError:
            stored_monday = None
        if stored_monday is not None and monday < stored_monday:
            return _fallback_proverb_line(list(cache.get("catalog") or []), day)

    fresh = _fetch_tounou_catalog()
    if fresh:
        catalog, pending = _merge_proverb_catalog(
            list(cache.get("catalog") or []),
            list(cache.get("pending_ids") or []),
            fresh,
        )
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    elif cache.get("catalog"):
        logger.warning("morning_brief: tounou catalog refresh failed; using previous cache")
        catalog = list(cache.get("catalog") or [])
        pending = [str(pid) for pid in (cache.get("pending_ids") or [])]
        fetched_at = str(cache.get("fetched_at") or "")
    else:
        return _legacy_proverb_line(day)

    if not catalog:
        return None

    week_assignments, pending = _assign_proverb_week(catalog, pending, monday)
    merged = _prune_assignments(dict(assignments), monday)
    merged.update(week_assignments)
    _save_proverb_cache(
        {
            "week_start": monday.isoformat(),
            "fetched_at": fetched_at,
            "pending_ids": pending,
            "catalog": catalog,
            "assignments": merged,
        }
    )
    logger.info(
        "morning_brief: proverb week %s catalog=%s pending=%s",
        monday.isoformat(),
        len(catalog),
        len(pending),
    )
    return merged.get(day.isoformat())


def build_jp_proverb_line(day: date) -> Optional[str]:
    try:
        return _proverb_line_for_day(day)
    except Exception as exc:
        logger.warning("morning_brief: proverb line failed: %s", exc)
        return _legacy_proverb_line(day)


def _format_jp_proverb_line(
    title: str,
    meaning: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    proverb = _normalize_proverb_title(title)
    speaker = str(author or "").strip()
    if speaker:
        return f"**格言** {proverb} — {speaker}（{TOUNOU_ATTRIBUTION}）"
    note = str(meaning or "").strip()
    if note:
        return f"**格言** {proverb} — {note}（{TOUNOU_ATTRIBUTION}）"
    return f"**格言** {proverb}（{TOUNOU_ATTRIBUTION}）"


def _fetch_zenquotes_today() -> Optional[str]:
    try:
        resp = requests.get("https://zenquotes.io/api/today", timeout=10)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as exc:
        logger.warning("morning_brief: zenquotes failed: %s", exc)
        return None
    if not rows:
        return None
    row = rows[0]
    quote = str(row.get("q") or "").strip()
    author = str(row.get("a") or "").strip()
    if not quote:
        return None
    if author:
        return f'**Quote** "{quote}" — {author} (ZenQuotes)'
    return f'**Quote** "{quote}" (ZenQuotes)'


def build_breath_second_line(day: date, region: str) -> Optional[str]:
    region_n = (region or "jp").lower()
    if region_n == "jp":
        return build_jp_proverb_line(day)
    return _fetch_zenquotes_today()


def build_morning_brief_lines(
    business_day: date,
    region: str,
    *,
    include_market: bool = True,
) -> MorningBriefLines:
    day = delivery_day_for_business_day(business_day)
    region_n = (region or "jp").lower()
    calendar = build_calendar_line(day, region_n, observation_day=business_day)
    fx_line = stock_line = None
    if include_market and not _morning_brief_market_disabled():
        fx_line, stock_line = build_market_lines(region_n)
    history = build_history_line(day, region_n)
    second = build_breath_second_line(day, region_n)
    return MorningBriefLines(
        calendar=calendar,
        fx=fx_line,
        stock=stock_line,
        history=history,
        breath_second=second,
    )


def _morning_brief_market_disabled() -> bool:
    flag = (os.getenv("MORNING_BRIEF_SKIP_MARKET") or "").strip().lower()
    return flag in ("1", "true", "yes", "on")


def morning_brief_enabled() -> bool:
    flag = (os.getenv("MORNING_BRIEF_ENABLED") or "true").strip().lower()
    return flag not in ("0", "false", "no", "off")


def render_morning_brief_markdown(
    business_day: date,
    region: str,
    *,
    lines: Optional[MorningBriefLines] = None,
) -> str:
    if not morning_brief_enabled():
        return ""
    region_n = (region or "jp").lower()
    data = lines or build_morning_brief_lines(business_day, region_n)
    sections: List[str] = []
    glance_lines = [data.calendar]
    if data.alert:
        glance_lines.append(data.alert)
    # 中身は配信日の日付・曜日・祝日のみ（動向コメントではない）
    if region_n == "us":
        sections.append("## 🗓 Today's calendar\n\n" + "\n".join(glance_lines))
    else:
        sections.append("## 🗓 今日のカレンダー\n\n" + "\n".join(glance_lines))
    market_lines = [x for x in (data.fx, data.stock) if x]
    if market_lines:
        if region_n == "us":
            sections.append("## 💹 Markets (through prior close)\n\n" + "\n".join(market_lines))
        else:
            sections.append("## 💹 マーケット（前日まで）\n\n" + "\n".join(market_lines))
    breath_lines = [x for x in (data.history, data.breath_second) if x]
    if breath_lines:
        if region_n == "us":
            sections.append("## ☕ A breath (history + quote)\n\n" + "\n".join(breath_lines))
        else:
            sections.append("## ☕ ひと息（歴史 + 格言）\n\n" + "\n".join(breath_lines))
    if not sections:
        return ""
    return "\n\n".join(sections) + "\n\n---\n"


@dataclass(frozen=True)
class WeeklyBriefLines:
    calendar: str
    fx: Optional[str] = None
    stock: Optional[str] = None
    history: Optional[str] = None
    breath_second: Optional[str] = None


def delivery_week_for_observation_week(week_sun: date) -> tuple[date, date]:
    """観測週（月〜日）の翌週 = 配信週（翌月曜〜日曜）。"""
    delivery_mon = week_sun + timedelta(days=1)
    return delivery_mon, delivery_mon + timedelta(days=6)


def build_week_calendar_line(week_mon: date, week_sun: date, region: str) -> str:
    """配信週の祝日一覧（なければ祝日なし）。"""
    region_n = (region or "jp").lower()
    holidays = _holiday_map_for_day(week_mon, region_n)
    in_week: List[tuple[date, str]] = []
    for ds, name in sorted(holidays.items()):
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        if week_mon <= d <= week_sun:
            in_week.append((d, name))
    if region_n == "us":
        span = f"{_format_short_date(week_mon, region_n)}-{_format_short_date(week_sun, region_n)}"
        if not in_week:
            return f"**This week** {span} · No public holidays"
        bits = ", ".join(
            f"{_format_short_date(d, region_n)} {n}" for d, n in in_week
        )
        return f"**This week** {span} · Holidays: {bits}"
    span = f"{_format_short_date(week_mon, region_n)}〜{_format_short_date(week_sun, region_n)}"
    if not in_week:
        return f"**今週** {span} · 祝日なし"
    bits = "、".join(f"{_format_short_date(d, region_n)}{n}" for d, n in in_week)
    return f"**今週** {span} · 祝日: {bits}"


def _fetch_yahoo_close_on_or_before(ticker: str, day: date) -> Optional[float]:
    """day 以前の直近終値。"""
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("morning_brief: yfinance not installed")
        return None
    start = day - timedelta(days=10)
    end = day + timedelta(days=1)
    try:
        hist = yf.Ticker(ticker).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True
        )
    except Exception as exc:
        logger.warning("morning_brief: yfinance range failed for %s: %s", ticker, exc)
        return None
    if hist is None or hist.empty:
        return None
    closes = hist["Close"].dropna()
    if closes.empty:
        return None
    for ts in reversed(list(closes.index)):
        try:
            d = ts.date()
        except Exception:
            continue
        if d <= day:
            return float(closes.loc[ts])
    return float(closes.iloc[-1])


def _week_return_pct(
    ticker: str, week_mon: date, week_sun: date
) -> Optional[tuple[float, float, float]]:
    """観測週の週次リターン（前週末終値 → 週末終値）。"""
    start_close = _fetch_yahoo_close_on_or_before(ticker, week_mon - timedelta(days=1))
    end_close = _fetch_yahoo_close_on_or_before(ticker, week_sun)
    if start_close is None or end_close is None or start_close == 0:
        return None
    pct = (end_close - start_close) / start_close * 100.0
    return start_close, end_close, pct


def build_week_market_lines(
    week_mon: date, week_sun: date, region: str
) -> tuple[Optional[str], Optional[str]]:
    region_n = (region or "jp").lower()
    fx = _week_return_pct("USDJPY=X", week_mon, week_sun)
    fx_line: Optional[str] = None
    if fx:
        _start, end, pct = fx
        if region_n == "us":
            fx_line = f"**FX** USD/JPY {end:.1f} (week {_signed_pct(pct)})"
        else:
            fx_line = f"**為替** USD/JPY {end:.1f}（週次 {_signed_pct(pct)}）"
    index_ticker = "^N225" if region_n == "jp" else "^GSPC"
    index_label = "日経" if region_n == "jp" else "S&P 500"
    idx = _week_return_pct(index_ticker, week_mon, week_sun)
    stock_line: Optional[str] = None
    if idx:
        _start, end, pct = idx
        if region_n == "us":
            stock_line = (
                f"**Stocks** {index_label} {end:,.2f} (week {_signed_pct(pct)})"
            )
        else:
            stock_line = (
                f"**株** {index_label} {end:,.0f}（週次 {_signed_pct(pct)}）"
            )
    return fx_line, stock_line


def build_week_breath_lines(
    week_mon: date,
    week_sun: date,
    region: str,
    *,
    include_proverb: bool = True,
) -> tuple[Optional[str], Optional[str]]:
    """観測週の代表日（水曜）の歴史 + 週固定の格言。"""
    mid = week_mon + timedelta(days=min(2, (week_sun - week_mon).days))
    region_n = (region or "jp").lower()
    history = build_history_line(mid, region_n)
    history = _rewrite_history_line_for_weekly(history, region_n)
    second = (
        build_breath_second_line(week_mon, region_n) if include_proverb else None
    )
    return history, second


_JP_WEEKLY_HISTORY_DATE_RE = re.compile(
    r"^\*\*歴史\*\*\s+\d{1,2}/\d{1,2}\s*·\s*(.+)$",
    re.DOTALL,
)


def _rewrite_history_line_for_weekly(
    history: Optional[str], region: str
) -> Optional[str]:
    """週次では日次の『この日』感を弱める（特定の暦日を前面に出さない）。"""
    if not history:
        return history
    if region == "us" and history.startswith("**On this day**"):
        return history.replace("**On this day**", "**This week in history**", 1)
    if region == "jp":
        m = _JP_WEEKLY_HISTORY_DATE_RE.match(history.strip())
        if m:
            return f"**今週の歴史** {m.group(1).strip()}"
    return history


def build_weekly_brief_lines(
    week_mon: date,
    week_sun: date,
    region: str,
    *,
    include_market: bool = True,
) -> WeeklyBriefLines:
    region_n = (region or "jp").lower()
    delivery_mon, delivery_sun = delivery_week_for_observation_week(week_sun)
    calendar = build_week_calendar_line(delivery_mon, delivery_sun, region_n)
    fx_line = stock_line = None
    if include_market and not _morning_brief_market_disabled():
        fx_line, stock_line = build_week_market_lines(week_mon, week_sun, region_n)
    # 週次メールは格言を出さない。日次側の未出キューをここで消費しない。
    history, second = build_week_breath_lines(
        week_mon, week_sun, region_n, include_proverb=False
    )
    return WeeklyBriefLines(
        calendar=calendar,
        fx=fx_line,
        stock=stock_line,
        history=history,
        breath_second=second,
    )


def render_weekly_brief_markdown(
    week_mon: date,
    week_sun: date,
    region: str,
    *,
    lines: Optional[WeeklyBriefLines] = None,
) -> str:
    """週次メール冒頭。為替・株だけ。カレンダーとひと息は日次側に残す。"""
    if not morning_brief_enabled():
        return ""
    region_n = (region or "jp").lower()
    data = lines or build_weekly_brief_lines(week_mon, week_sun, region_n)
    market_lines = [x for x in (data.fx, data.stock) if x]
    if not market_lines:
        return ""
    market_heading = (
        "## 💹 Markets (last week)"
        if region_n == "us"
        else "## 💹 マーケット（先週）"
    )
    return market_heading + "\n\n" + "\n".join(market_lines) + "\n\n---\n"

