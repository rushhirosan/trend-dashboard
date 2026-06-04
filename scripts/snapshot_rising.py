"""
07 / 13 / 19 スナップショット横断の「急上昇」選定ロジック。

``generate_ai_daily_summary`` と ``generate_daily_x_post_series`` で
判断軸（jump 計算・候補資格・ノイズ除外・表示ラベル）を共有する。
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote_plus, urlparse

DAYTIME_SLOTS = ("07", "13", "19")

WEAK_RISING_LABEL = re.compile(
    r"^(pickup|official|news|video|動画|ニュース|…+)$",
    re.I,
)
NOISY_PROCUREMENT = re.compile(
    r"(LICENSE\s+RENEWAL|POP:\s*\d|INFINIBAND|FIBRE\s+OPTIC|usaspending|調達|契約番号)",
    re.I,
)


def snapshot_top_n() -> int:
    try:
        return max(1, min(25, int(os.getenv("TREND_SNAPSHOT_TOP_N", "10"))))
    except (TypeError, ValueError):
        return 10


def rank_out_of_range() -> int:
    return snapshot_top_n() + 1


def normalize_label_key(t: str) -> str:
    return re.sub(r"\s+", " ", str(t).strip()).lower()[:600]


def clean_rising_display(display: str) -> str:
    s = re.sub(r"^【[^】]{1,16}】\s*", "", str(display).strip())
    return re.sub(r"\s+", " ", s).strip()


def is_weak_rising_label(display: str) -> bool:
    s = clean_rising_display(display)
    if not s or s == "…" or len(s) < 4:
        return True
    return bool(WEAK_RISING_LABEL.match(s))


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars / len(text)


def series_pref_score(series_key: str) -> int:
    sk = (series_key or "").lower()
    if sk.endswith("_jp") or "_jp_" in sk:
        return 3
    if sk.endswith("_us") or "_us_" in sk:
        return 0
    return 1


def is_noisy_label(display: str, series_key: str = "") -> bool:
    """調達行・英語長文など、一般読者向けから除外するラベル。"""
    if is_weak_rising_label(display):
        return True
    s = clean_rising_display(display)
    sk = (series_key or "").lower()
    if len(s) > 100:
        return True
    if NOISY_PROCUREMENT.search(s):
        return True
    if any(p in sk for p in ("usaspending_", "kkj_", "estat_", "bls_")) and len(s) > 45:
        return True
    if _ascii_ratio(s) > 0.88 and len(s) > 50 and series_pref_score(series_key) < 2:
        return True
    return False


def rank_jump_score(ranks: dict[str, int]) -> float:
    """07→13→19 の隣接差分合計（上昇は加点、下落は減点）。未掲載スロットは圏外順位。"""
    oor = rank_out_of_range()
    prev_eff: Optional[int] = None
    s = 0.0
    for slot in DAYTIME_SLOTS:
        cur = int(ranks[slot]) if slot in ranks else oor
        if prev_eff is not None:
            s += float(prev_eff - cur)
        prev_eff = cur
    return s


def rising_qualifies(ranks: dict[str, int], jump: float) -> bool:
    """正の net jump、2スロット以上掲載、実観測で終わりだけ悪化は除外。"""
    if jump <= 0:
        return False
    observed = [(s, int(ranks[s])) for s in DAYTIME_SLOTS if s in ranks]
    if len(observed) < 2:
        return False
    if observed[-1][1] > observed[0][1]:
        return False
    return True


def daytime_best_rank(ranks: dict[str, int]) -> int:
    vals = [int(ranks[s]) for s in DAYTIME_SLOTS if s in ranks]
    return min(vals) if vals else 999


def pick_display_from_agg(agg: dict[str, Any]) -> str:
    """表示ラベルは一日の最良順位が出たスロットの表記を優先。"""
    ranks = agg.get("ranks") or {}
    by_slot = agg.get("display_by_slot") or {}
    best_slot: Optional[str] = None
    best_r = 999
    for slot in DAYTIME_SLOTS:
        r = ranks.get(slot)
        if r is not None and int(r) < best_r:
            best_r = int(r)
            best_slot = slot
    if best_slot:
        d = by_slot.get(best_slot)
        if d:
            return clean_rising_display(str(d))
    for slot in DAYTIME_SLOTS:
        d = by_slot.get(slot)
        if d:
            return clean_rising_display(str(d))
    return ""


def aggregate_labels_for_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for slot in DAYTIME_SLOTS:
        items = (series_by_slot.get(slot) or {}).get(series_key) or []
        for it in items:
            if not isinstance(it, dict):
                continue
            raw_t = it.get("t")
            if raw_t is None or not str(raw_t).strip():
                continue
            display = str(raw_t).strip()
            nk = normalize_label_key(display)
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


def collect_rising_candidates(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_keys: tuple[str, ...] | list[str],
    *,
    display_postprocess: Callable[[str, str], str] | None = None,
    tail_for_series: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """全 series 横断。ラベルキーごとに最良候補を1つ。資格・ノイズ済み。"""
    best: dict[str, dict[str, Any]] = {}
    for series_key in series_keys:
        aggs = aggregate_labels_for_series(series_by_slot, series_key)
        tail = (tail_for_series(series_key) if tail_for_series else "")
        for nk, agg in aggs.items():
            ranks = agg.get("ranks") or {}
            jump = rank_jump_score(ranks)
            raw_display = pick_display_from_agg(agg)
            if display_postprocess:
                raw_display = display_postprocess(series_key, raw_display)
            display = clean_rising_display(raw_display)
            if not display or not rising_qualifies(ranks, jump) or is_noisy_label(
                display, series_key
            ):
                continue
            freq = len(set(ranks.keys()) & set(DAYTIME_SLOTS))
            r_best = daytime_best_rank(ranks)
            cand = {
                "nk": nk,
                "display": display,
                "tail": tail,
                "jump": jump,
                "freq": freq,
                "r_best": r_best,
                "series_key": series_key,
                "ranks": dict(ranks),
            }
            prev = best.get(nk)
            if prev is None or (cand["jump"], cand["freq"], -cand["r_best"]) > (
                prev["jump"],
                prev["freq"],
                -prev["r_best"],
            ):
                best[nk] = cand
    return list(best.values())


def pick_top_rising(
    candidates: list[dict[str, Any]],
    *,
    count: int,
) -> list[dict[str, Any]]:
    """jump 降順で最大 count 件（同軸は AI サマリーと同じ）。"""
    items = sorted(
        candidates,
        key=lambda c: (-c["jump"], -c["freq"], c["r_best"], c["display"]),
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in items:
        nk = c.get("nk") or ""
        if nk in seen:
            continue
        seen.add(nk)
        out.append(c)
        if len(out) >= count:
            break
    return out


_SLOTS_URL_ORDER = ("19", "13", "07", "01")


def url_from_thin_item(item: dict[str, Any]) -> Optional[str]:
    u = item.get("u")
    if u is None:
        return None
    s = str(u).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return None


def normalize_article_url(url: str) -> Optional[str]:
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


def url_for_label_in_series(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    label: str,
) -> Optional[str]:
    """系列内でラベルに対応する記事 URL（19→13→07→01 の順）。"""
    nk = normalize_label_key(label)
    for slot in _SLOTS_URL_ORDER:
        for it in (series_by_slot.get(slot) or {}).get(series_key) or []:
            if not isinstance(it, dict):
                continue
            if normalize_label_key(str(it.get("t") or "")) == nk:
                u = url_from_thin_item(it)
                if u:
                    return u
    return None


def fallback_search_url(label: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(clean_rising_display(label))}"


def article_url_for_rising(
    series_by_slot: dict[str, dict[str, list[Any]]],
    series_key: str,
    display: str,
) -> str:
    """急上昇表示用 URL。スナップに u が無ければ Google 検索。"""
    return url_for_label_in_series(series_by_slot, series_key, display) or fallback_search_url(
        display
    )
