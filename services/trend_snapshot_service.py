"""
定期ジョブ完了後にキャッシュから薄いスナップショットを保存する。

7時起点の business_day:
  - スロット 07 / 13 / 19 は「その日」の business_day
  - スロット 01（深夜1時台ジョブ）は「前日」の business_day を閉じる（scheduler の slot_key の暦日は実行日）
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytz
from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)

JST = pytz.timezone("Asia/Tokyo")


def parse_scheduler_slot_key(
    scheduler_slot_key: Optional[str],
) -> Optional[Tuple[date, str]]:
    """
    scheduler の slot_key（例: 7am_2026-05-02）を
    (business_day, slot_code) に変換する。

    slot_code は '01'|'07'|'13'|'19'。
    深夜1時台（1am_YYYY-MM-DD）は business_day が「その暦日の前日」。
    """
    if not scheduler_slot_key or "_" not in scheduler_slot_key:
        return None
    idx = scheduler_slot_key.find("_")
    prefix = scheduler_slot_key[:idx]
    date_str = scheduler_slot_key[idx + 1 :]
    try:
        cal = date.fromisoformat(date_str)
    except ValueError:
        return None

    mapping = {
        "1am": ("01", cal - timedelta(days=1)),
        "7am": ("07", cal),
        "1pm": ("13", cal),
        "7pm": ("19", cal),
    }
    if prefix not in mapping:
        return None
    slot_code, business_day = mapping[prefix]
    return business_day, slot_code


def _top_n() -> int:
    try:
        return max(1, min(25, int(os.getenv("TREND_SNAPSHOT_TOP_N", "10"))))
    except (TypeError, ValueError):
        return 10


def _exclude_market() -> bool:
    # 既定 false: JP/US 株・暗号を日次サマリー用スナップショットに含める。
    return os.getenv("TREND_SNAPSHOT_EXCLUDE_MARKET", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def _enabled() -> bool:
    return os.getenv("TREND_SNAPSHOTS_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _dummy_mode() -> bool:
    return os.getenv("USE_DUMMY_DATA", "").strip().lower() in ("true", "1", "yes")


def _label_from_item(item: Any, idx: int) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    text = None
    for k in (
        "title",
        "keyword",
        "name",
        "term",
        "repo",
        "name_ja",
        "name_en",
        "vulnerability_name",
        "agency_name",
        "indicator_id",
        "cve_id",
    ):
        v = item.get(k)
        if v is not None and str(v).strip():
            text = str(v).strip()[:500]
            break
    if not text:
        return None
    rank = item.get("rank")
    if rank is None:
        rank = idx + 1
    try:
        rank = int(rank)
    except (TypeError, ValueError):
        rank = idx + 1
    out: Dict[str, Any] = {"t": text, "r": rank}
    # YouTube は video_id のみ、Google Trends は google_search_url、映画/書籍は item_url 等。
    for uk in (
        "url",
        "link",
        "html_url",
        "news_url",
        "google_search_url",
        "item_url",
        "affiliate_url",
        "amazon_link",
    ):
        raw_u = item.get(uk)
        if raw_u is None:
            continue
        u = str(raw_u).strip()
        if u.startswith("http://") or u.startswith("https://"):
            out["u"] = u[:2000]
            break
    if "u" not in out:
        vid = item.get("video_id")
        if vid is not None and str(vid).strip():
            out["u"] = f"https://www.youtube.com/watch?v={str(vid).strip()}"[:2000]
    return out


def _items_from_data_list(data: Any, limit: int) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(data[:limit]):
        lab = _label_from_item(row, i)
        if lab:
            out.append(lab)
    return out


def _items_from_usaspending_payload(payload: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """USAspending の dict payload を snapshot 用の薄い配列へ変換する。"""
    out: List[Dict[str, Any]] = []
    top_cases = payload.get("keyword_top_cases")
    if isinstance(top_cases, dict):
        # ai / dx / cyber の順で優先し、rank は通し番号にする。
        for cat in ("ai", "dx", "cyber"):
            rows = top_cases.get(cat)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                title = row.get("title")
                if title is None or not str(title).strip():
                    continue
                out.append({"t": str(title).strip()[:500], "r": len(out) + 1})
                if len(out) >= limit:
                    return out
    return out


def _safe_call_series(
    series_key: str,
    fetch: Callable[[], Any],
    limit: int,
) -> Tuple[str, List[Dict[str, Any]]]:
    try:
        res = fetch()
        if not res or not isinstance(res, dict):
            return series_key, []
        # BaseTrendsManager は success を付ける。省略されている旧実装は data があれば許容する。
        if res.get("success") is False:
            return series_key, []
        if res.get("success") is None:
            if res.get("error") and "data" not in res:
                return series_key, []
            if "data" not in res:
                return series_key, []
        data = res.get("data")
        if data is None:
            return series_key, []
        if series_key == "usaspending_us" and isinstance(data, dict):
            return series_key, _items_from_usaspending_payload(data, limit)
        if isinstance(data, dict) and "data" in data:
            inner = data.get("data")
            if isinstance(inner, list):
                return series_key, _items_from_data_list(inner, limit)
            return series_key, []
        if isinstance(data, list):
            return series_key, _items_from_data_list(data, limit)
        return series_key, []
    except Exception as e:
        logger.warning("⚠️ snapshot series %s: %s", series_key, e)
        return series_key, []


def _kkj_items(mgr: Any, limit: int) -> List[Dict[str, Any]]:
    try:
        res = mgr.get_public_sector_signals(force_refresh=False, cache_only=True)
        if not res or not res.get("success"):
            return []
        payload = res.get("data")
        if not isinstance(payload, dict):
            return []
        signals = payload.get("signals") or []
        out: List[Dict[str, Any]] = []
        if isinstance(signals, list):
            for i, s in enumerate(signals[:limit]):
                if isinstance(s, dict):
                    t = (
                        s.get("keyword")
                        or s.get("title")
                        or s.get("query")
                        or str(s)[:120]
                    )
                else:
                    t = str(s)[:120]
                if t:
                    out.append({"t": str(t).strip()[:500], "r": i + 1})
        return out
    except Exception as e:
        logger.warning("⚠️ snapshot kkj: %s", e)
        return []


def collect_series_snapshots(managers: Dict[str, Any]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """キャッシュのみから各 series のスナップショット配列を返す。"""
    limit = _top_n()
    ex_market = _exclude_market()
    out: List[Tuple[str, List[Dict[str, Any]]]] = []

    def add(series_key: str, fetch: Callable[[], Any]) -> None:
        sk, items = _safe_call_series(series_key, fetch, limit)
        out.append((sk, items))

    g = managers.get("google")
    if g:
        add("google_trends_jp", lambda: g.get_trends("JP", limit=25, force_refresh=False))
        add("google_trends_us", lambda: g.get_trends("US", limit=25, force_refresh=False))

    yt = managers.get("youtube")
    if yt:
        add(
            "youtube_trends_jp",
            lambda: yt.get_trends("JP", max_results=25, force_refresh=False),
        )
        add(
            "youtube_trends_us",
            lambda: yt.get_trends("US", max_results=25, force_refresh=False),
        )

    mu = managers.get("music")
    if mu:
        add(
            "music_trends_jp",
            lambda: mu.get_trends("spotify", "JP", force_refresh=False),
        )
        add(
            "music_trends_us",
            lambda: mu.get_trends("spotify", "US", force_refresh=False),
        )

    wn = managers.get("worldnews")
    if wn:
        add(
            "worldnews_jp",
            lambda: wn.get_trends(
                country="jp", category=None, page_size=25, force_refresh=False
            ),
        )
        add(
            "worldnews_us",
            lambda: wn.get_trends(
                country="us", category=None, page_size=25, force_refresh=False
            ),
        )

    po = managers.get("podcast")
    if po:
        add(
            "podcast_jp",
            lambda: po.get_trends(
                "best_podcasts", region="jp", page_size=25, force_refresh=False
            ),
        )
        add(
            "podcast_us",
            lambda: po.get_trends(
                "best_podcasts", region="us", page_size=25, force_refresh=False
            ),
        )

    ra = managers.get("rakuten")
    if ra:
        add(
            "rakuten_jp",
            lambda: ra.get_trends(
                force_refresh=False, fetch_all_categories=False, limit=25
            ),
        )

    ha = managers.get("hatena")
    if ha:
        add(
            "hatena_jp",
            lambda: ha.get_trends(
                category="all",
                limit=25,
                force_refresh=False,
                fetch_all_categories=False,
            ),
        )

    tw = managers.get("twitch")
    if tw and os.getenv("TWITCH_CLIENT_ID") and os.getenv("TWITCH_CLIENT_SECRET"):
        add(
            "twitch_jp",
            lambda: tw.get_trends(category="games", limit=25, force_refresh=False),
        )
        add(
            "twitch_us",
            lambda: tw.get_trends(category="games", limit=25, force_refresh=False),
        )

    qi = managers.get("qiita")
    if qi:
        add(
            "qiita_jp",
            lambda: qi.get_trends(limit=25, sort="likes_count", force_refresh=False),
        )

    nk = managers.get("nhk")
    if nk:
        add("nhk_jp", lambda: nk.get_trends(limit=25, force_refresh=False))

    pr = managers.get("prtimes")
    if pr:
        add("prtimes_jp", lambda: pr.get_trends(limit=25, force_refresh=False))

    prh = managers.get("prtimes_hatena")
    if prh:
        add("prtimes_hatena_jp", lambda: prh.get_trends(limit=5, force_refresh=False))

    if not ex_market:
        st = managers.get("stock")
        if st:
            add(
                "stock_jp",
                lambda: st.get_trends(market="JP", limit=25, force_refresh=False),
            )
            add(
                "stock_us",
                lambda: st.get_trends(market="US", limit=25, force_refresh=False),
            )
        cr = managers.get("crypto")
        if cr:
            add("crypto_global", lambda: cr.get_trends(limit=25, force_refresh=False))

    mo = managers.get("movie")
    if mo:
        add(
            "movie_jp",
            lambda: mo.get_trends(
                country="JP", time_window="day", limit=25, force_refresh=False
            ),
        )
        add(
            "movie_us",
            lambda: mo.get_trends(
                country="US", time_window="day", limit=25, force_refresh=False
            ),
        )

    bk = managers.get("book")
    if bk:
        for cat in ("all", "fiction", "business", "humanities", "practical"):
            add(
                f"book_jp_{cat}",
                lambda m=bk, c=cat: m.get_trends(
                    country="JP", limit=25, force_refresh=False, category=c
                ),
            )
        for cat in ("all", "fiction", "business", "biography", "science"):
            add(
                f"book_us_{cat}",
                lambda m=bk, c=cat: m.get_trends(
                    country="US", limit=25, force_refresh=False, category=c
                ),
            )

    gh = managers.get("github")
    if gh:
        add(
            "github_jp",
            lambda: gh.get_trends(language="all", limit=25, force_refresh=False),
        )
        add(
            "github_us",
            lambda: gh.get_trends(language="all", limit=25, force_refresh=False),
        )

    ap = managers.get("appstore")
    if ap:
        add(
            "appstore_jp",
            lambda: ap.get_trends(
                country="JP", category="all", limit=25, force_refresh=False
            ),
        )
        add(
            "appstore_us",
            lambda: ap.get_trends(
                country="US", category="all", limit=25, force_refresh=False
            ),
        )

    ipa = managers.get("ipa")
    if ipa:
        add("ipa_jp", lambda: ipa.get_trends(limit=25, force_refresh=False))

    jpcc = managers.get("jpcert")
    if jpcc:
        add("jpcert_jp", lambda: jpcc.get_trends(limit=25, force_refresh=False))

    zn = managers.get("zenn")
    if zn:
        add("zenn_jp", lambda: zn.get_trends(limit=25, force_refresh=False))

    nt = managers.get("note")
    if nt:
        add(
            "note_jp",
            lambda: nt.get_trends(
                category="all",
                limit=25,
                force_refresh=False,
                fetch_all_categories=False,
            ),
        )

    wiki = managers.get("wikipedia")
    if wiki:
        add(
            "wikipedia_ja",
            lambda: wiki.get_trends(lang="ja", limit=25, force_refresh=False),
        )
        add(
            "wikipedia_en",
            lambda: wiki.get_trends(lang="en", limit=25, force_refresh=False),
        )

    es = managers.get("estat")
    if es:
        add(
            "estat_jp",
            lambda: es.get_trends(limit=6, force_refresh=False),
        )

    kkj = managers.get("kkj")
    if kkj:
        out.append(("kkj_jp", _kkj_items(kkj, limit)))

    eb = managers.get("ebay")
    if eb:
        try:
            cats = eb.get_available_categories() or []
            first = cats[0] if cats else "fashion"

            def _ebay_fetch():
                return eb.get_trends(category=first, limit=25, force_refresh=False)

            add("ebay_us", _ebay_fetch)
        except Exception as e:
            logger.warning("⚠️ snapshot ebay: %s", e)

    hn = managers.get("hackernews")
    if hn:
        add(
            "hackernews_us",
            lambda: hn.get_trends("top", limit=25, force_refresh=False),
        )

    ph = managers.get("producthunt")
    if ph:
        add(
            "producthunt_us",
            lambda: ph.get_trends(limit=25, sort="votes", force_refresh=False),
        )

    cn = managers.get("cnn")
    if cn:
        add("cnn_us", lambda: cn.get_trends(limit=25, force_refresh=False))

    gn = managers.get("globenewswire")
    if gn:
        add(
            "globenewswire_us",
            lambda: gn.get_trends(limit=25, force_refresh=False),
        )

    gnm = managers.get("globenewswire_market_reaction")
    if gnm:
        add(
            "globenewswire_market_us",
            lambda: gnm.get_trends(limit=15, force_refresh=False),
        )

    cisa = managers.get("cisa_kev")
    if cisa:
        add("cisa_kev_us", lambda: cisa.get_trends(limit=25, force_refresh=False))

    thn = managers.get("thehackernews")
    if thn:
        add("thehackernews_us", lambda: thn.get_trends(limit=25, force_refresh=False))

    med = managers.get("medium")
    if med:
        add("medium_us", lambda: med.get_trends(limit=25, force_refresh=False))

    dv = managers.get("devto")
    if dv:
        add("devto_us", lambda: dv.get_trends(limit=25, force_refresh=False))

    bls = managers.get("bls")
    if bls:
        add("bls_us", lambda: bls.get_trends(limit=10, force_refresh=False))

    usa = managers.get("usaspending")
    if usa:
        add("usaspending_us", lambda: usa.get_trends(force_refresh=False))

    oa = managers.get("openalex")
    if oa:
        for cat in (
            "trending",
            "ai",
            "nlp",
            "climate",
            "biotech",
            "quantum",
            "medical",
        ):
            add(
                f"openalex_{cat}_jp",
                lambda m=oa, c=cat: m.get_trends(
                    category=c, limit=25, force_refresh=False, region="jp"
                ),
            )
            add(
                f"openalex_{cat}_us",
                lambda m=oa, c=cat: m.get_trends(
                    category=c, limit=25, force_refresh=False, region="us"
                ),
            )

    bs = managers.get("bluesky")
    if bs:
        add(
            "bluesky_jp",
            lambda: bs.get_trends(limit=25, force_refresh=False, region="jp"),
        )
        add(
            "bluesky_us",
            lambda: bs.get_trends(limit=25, force_refresh=False, region="us"),
        )

    return out


def write_snapshots_for_scheduler_run(
    managers: Dict[str, Any],
    scheduler_slot_key: Optional[str],
    trigger_source: str,
    captured_at: Optional[datetime] = None,
) -> bool:
    """
    スケジューラ完了後に呼ぶ。scheduler_slot_key はジョブ開始時の slot_key（終了時刻ではなく）
    を渡すこと。
    """
    if not _enabled():
        logger.info("⏭️ トレンドスナップショット無効（TREND_SNAPSHOTS_ENABLED=false）")
        return False
    if _dummy_mode():
        logger.info("⏭️ ダミーモードのためスナップショット保存をスキップ")
        return False

    parsed = parse_scheduler_slot_key(scheduler_slot_key)
    if not parsed:
        logger.info(
            "⏭️ scheduler_slot_key が不明のためスナップショット保存をスキップ: %s",
            scheduler_slot_key,
        )
        return False

    business_day, slot_code = parsed
    cap = captured_at or datetime.now(JST)
    if cap.tzinfo is None:
        cap = JST.localize(cap)
    else:
        cap = cap.astimezone(JST)

    pairs = collect_series_snapshots(managers)
    rows = []
    for series_key, items in pairs:
        rows.append((business_day, slot_code, series_key, items, cap))

    db = TrendsCache()
    ok = db.upsert_trend_daily_snapshots_batch(rows)
    if ok:
        logger.info(
            "✅ トレンドスナップショット保存: business_day=%s slot=%s series=%s件",
            business_day.isoformat(),
            slot_code,
            len(rows),
        )
    return ok
