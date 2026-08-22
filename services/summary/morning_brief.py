"""朝便り（カレンダー・マーケット・ひと息）を日次サマリー冒頭用 Markdown で組み立てる。"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import requests

from utils.logger_config import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
TOUNOU_RSS_URL = "https://meigen.tounou.net/?feed=rss2"
TOUNOU_ATTRIBUTION = "10秒名言"

HTTP_HEADERS = {
    "User-Agent": (
        "TrendDashboardSummary/1.0 "
        "(https://trends-dashboard.com; summary-bot@trends-dashboard.com)"
    )
}

WIKI_UA = HTTP_HEADERS["User-Agent"]

JP_WEEKDAYS = ("月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜")
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


def _weekday_label(day: date, region: str) -> str:
    if (region or "jp").lower() == "us":
        return US_WEEKDAYS[day.weekday()]
    return JP_WEEKDAYS[day.weekday()]


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


def _clip(text: str, max_len: int) -> str:
    s = str(text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


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


def build_calendar_line(day: date, region: str) -> str:
    region_n = (region or "jp").lower()
    weekday = _weekday_label(day, region_n)
    holidays = _holiday_map_for_day(day, region_n)
    iso = day.isoformat()
    if iso in holidays:
        label = _format_short_date(day, region_n)
        name = holidays[iso]
        if region_n == "us":
            return f"**Calendar** {weekday} · Today: {label} {name}"
        return f"**カレンダー** {weekday} · 今日は {label}{name}（祝日）"
    upcoming: List[tuple[date, str]] = []
    for ds, name in sorted(holidays.items()):
        try:
            d = date.fromisoformat(ds)
        except ValueError:
            continue
        if d > day:
            upcoming.append((d, name))
    if region_n == "us":
        base = f"**Calendar** {weekday}"
        if not upcoming:
            return base
        nd, name = upcoming[0]
        return f"{base} · Next holiday: {_format_short_date(nd, region_n)} {name}"
    base = f"**カレンダー** {weekday}"
    if not upcoming:
        return base
    nd, name = upcoming[0]
    return f"{base} · 次の祝日は {_format_short_date(nd, region_n)}{name}"


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
    text = _strip_wikitext(str(items[0].get("text") or ""))
    if not text:
        return None
    year_match = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text)
    if year_match:
        year = year_match.group(1)
        rest = text[year_match.end() :].lstrip(" –—-,")
        rest = _clip(rest, 55)
        return f"**On this day** {year} — {rest} (Wikipedia)"
    return f"**On this day** {_clip(text, 80)} (Wikipedia)"


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
        year_match = re.search(r"(\d{1,4})年", cleaned)
        if not year_match:
            continue
        year = year_match.group(1)
        rest = cleaned[year_match.end() :].lstrip("—－-・ ")
        rest = re.split(r"[（(]", rest, maxsplit=1)[0].strip(" 　—-")
        rest = _clip(rest, 50)
        if not rest:
            continue
        return f"**歴史** {year}年 — {rest}（Wikipedia）"
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
    t = str(title or "").strip()
    if not t:
        return t
    if t.startswith("「"):
        return t
    if len(t) > 72:
        return _clip(t, 72)
    return f"「{t}」"


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
        return _clip(line, 45)
    return None


def _fetch_tounou_rss_items(*, max_items: int = 30) -> List[Dict[str, str]]:
    try:
        resp = requests.get(
            TOUNOU_RSS_URL,
            timeout=10,
            headers=HTTP_HEADERS,
        )
        resp.raise_for_status()
        if not resp.text.strip().startswith("<?xml"):
            logger.warning("morning_brief: tounou RSS returned non-xml")
            return []
        root = ET.fromstring(resp.text)
    except Exception as exc:
        logger.warning("morning_brief: tounou RSS fetch failed: %s", exc)
        return []
    out: List[Dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            out.append({"title": title, "link": link})
        if len(out) >= max_items:
            break
    return out


def _fetch_tounou_meaning(article_url: str) -> Optional[str]:
    try:
        resp = requests.get(article_url, timeout=12, headers=HTTP_HEADERS)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("morning_brief: tounou article fetch failed: %s", exc)
        return None
    lines = _extract_tounou_article_lines(resp.text)
    return _meaning_from_tounou_lines(lines)


def _select_tounou_item_for_day(items: List[Dict[str, str]], day: date) -> Optional[Dict[str, str]]:
    if not items:
        return None
    idx = day.toordinal() % len(items)
    return items[idx]


def _format_jp_proverb_line(title: str, meaning: Optional[str]) -> str:
    proverb = _normalize_proverb_title(title)
    if meaning:
        return f"**格言** {proverb} — {meaning}（{TOUNOU_ATTRIBUTION}）"
    return f"**格言** {proverb}（{TOUNOU_ATTRIBUTION}）"


def build_jp_proverb_line(day: date) -> Optional[str]:
    items = _fetch_tounou_rss_items()
    item = _select_tounou_item_for_day(items, day)
    if not item:
        return None
    meaning = _fetch_tounou_meaning(item["link"])
    return _format_jp_proverb_line(item["title"], meaning)


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
    quote = _clip(str(row.get("q") or "").strip(), 90)
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
    calendar = build_calendar_line(day, region_n)
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
    if region_n == "us":
        sections.append("## 🗓 Today at a glance\n\n" + "\n".join(glance_lines))
    else:
        sections.append("## 🗓 今日どう動くか\n\n" + "\n".join(glance_lines))
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
