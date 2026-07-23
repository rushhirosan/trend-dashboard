"""
スケジューラ shed 中など TREND_MANAGERS が無いときのキャッシュ直読み。

親プロセスに manager を再載せせず、TrendsCache だけ読んで画面用 API / SSR を満たす。
外部 API は呼ばない（force_refresh も無視）。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from database_config import TrendsCache
from utils.logger_config import get_logger

logger = get_logger(__name__)


def _limit(data: Optional[list], limit: Optional[int]) -> list:
    if not data:
        return []
    if limit is None or limit <= 0:
        return list(data)
    return list(data)[:limit]


def _google(db: TrendsCache, *, region: str = "JP", country: str | None = None, limit: int = 25, **_) -> list:
    r = (region or country or "JP").upper()
    if r in ("JAPAN",):
        r = "JP"
    cached = db.get_google_trends_from_cache(r) or []
    for item in cached:
        if "google_search_url" not in item and item.get("keyword"):
            kw = item["keyword"]
            item["google_search_url"] = f"https://www.google.com/search?q={kw.replace(' ', '+')}"
    return _limit(cached, limit)


def _youtube(
    db: TrendsCache,
    *,
    region_code: str | None = None,
    region: str | None = None,
    trend_type: str = "trending",
    limit: int = 25,
    max_results: int | None = None,
    **_,
) -> list:
    r = region_code or region or "JP"
    n = max_results if max_results is not None else limit
    return _limit(db.get_youtube_trends_from_cache(r, trend_type) or [], n)


def _music(db: TrendsCache, *, service: str = "spotify", region: str = "JP", limit: int = 25, **_) -> list:
    return _limit(db.get_music_trends_from_cache(service=service, region=region) or [], limit)


def _worldnews(
    db: TrendsCache,
    *,
    country: str = "jp",
    category: str | None = "general",
    limit: int = 25,
    page_size: int | None = None,
    **_,
) -> list:
    n = page_size if page_size is not None else limit
    c = (country or "jp").lower()
    return _limit(db.get_worldnews_trends_from_cache(category or "general", c) or [], n)


def _podcast(
    db: TrendsCache,
    *,
    trend_type: str = "best_podcasts",
    region: str = "JP",
    limit: int = 25,
    page_size: int | None = None,
    **_,
) -> list:
    n = page_size if page_size is not None else limit
    return _limit(db.get_podcast_trends_from_cache(trend_type=trend_type, region=region) or [], n)


def _rakuten(db: TrendsCache, *, genre_id: str = "all", category: str | None = None, limit: int = 25, **_) -> list:
    g = category or genre_id or "all"
    return _limit(db.get_rakuten_trends_from_cache(g) or [], limit)


def _hatena(db: TrendsCache, *, category: str = "all", limit: int = 25, **_) -> list:
    return _limit(db.get_hatena_trends_from_cache(category) or [], limit)


def _twitch(db: TrendsCache, *, category: str = "games", trend_type: str | None = None, limit: int = 25, **_) -> list:
    t = trend_type or category or "games"
    return _limit(db.get_twitch_trends_from_cache(t) or [], limit)


def _hackernews(db: TrendsCache, *, story_type: str = "top", limit: int = 25, **_) -> list:
    return _limit(db.get_hackernews_trends_from_cache(story_type) or [], limit)


def _qiita(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_qiita_trends_from_cache() or [], limit)


def _github(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_github_trends_from_cache() or [], limit)


def _appstore(db: TrendsCache, *, country: str = "JP", limit: int = 25, **_) -> list:
    return _limit(db.get_appstore_trends_from_cache(country) or [], limit)


def _nhk(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_nhk_trends_from_cache() or [], limit)


def _prtimes(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_prtimes_trends_from_cache() or [], limit)


def _prtimes_hatena(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_prtimes_hatena_trends_from_cache() or [], limit)


def _globenewswire(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_globenewswire_trends_from_cache() or [], limit)


def _globenewswire_market_reaction(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_globenewswire_market_reaction_trends_from_cache() or [], limit)


def _wikipedia(db: TrendsCache, *, lang: str = "ja", limit: int = 25, **_) -> list:
    return _limit(db.get_wikipedia_trends_from_cache(lang=lang) or [], limit)


def _producthunt(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_producthunt_trends_from_cache() or [], limit)


def _cnn(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_cnn_trends_from_cache() or [], limit)


def _stock(db: TrendsCache, *, market: str = "US", limit: int = 25, **_) -> list:
    return _limit(db.get_stock_trends_from_cache(market) or [], limit)


def _crypto(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_crypto_trends_from_cache() or [], limit)


def _movie(db: TrendsCache, *, country: str = "JP", limit: int = 25, **_) -> list:
    return _limit(db.get_movie_trends_from_cache(country) or [], limit)


def _book(db: TrendsCache, *, country: str = "JP", category: str = "all", limit: int = 25, **_) -> list:
    return _limit(db.get_book_trends_from_cache(country, category) or [], limit)


def _cisa_kev(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_cisa_kev_trends_from_cache() or [], limit)


def _estat(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_estat_trends_from_cache() or [], limit)


def _bls(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_bls_trends_from_cache() or [], limit)


def _usaspending(db: TrendsCache, **_) -> Any:
    return db.get_usaspending_trends_from_cache() or {}


def _kkj(db: TrendsCache, **_) -> Any:
    return db.get_kkj_trends_from_cache()


def _kkj_fill_defaults(cached: Optional[dict]) -> Optional[dict]:
    """KKJTrendsManager._kkj_fill_cache_defaults と同等（shed 中の形合わせ）。"""
    if cached is None:
        return None
    from services.trends.kkj_trends import KKJ_CATEGORY_LABELS, KKJ_CATEGORY_ORDER

    out = dict(cached)
    if "keyword_top_cases" not in out:
        out["keyword_top_cases"] = {}
    if "ranking_result_count" not in out:
        out["ranking_result_count"] = {}
    if "keyword_category" not in out:
        out["keyword_category"] = {}
    if "category_labels" not in out:
        out["category_labels"] = dict(KKJ_CATEGORY_LABELS)
    if "category_order" not in out:
        out["category_order"] = list(KKJ_CATEGORY_ORDER)
    return out


def _kkj_empty_payload() -> dict:
    from services.trends.kkj_trends import SIGNALS_MONTHS

    return {
        "signals": [],
        "signals_monthly": {},
        "prefecture_ranking": [],
        "prefecture_rankings": {},
        "keyword_top_cases": {},
        "ranking_result_count": {},
        "keyword_category": {},
        "category_labels": {},
        "category_order": [],
        "period_days": 30,
        "period_months": SIGNALS_MONTHS,
        "as_of": "",
    }


def _kkj_cached_result() -> dict:
    """KKJTrendsManager.get_public_sector_signals(cache_only=True) に近い形。"""
    cached = read_cached_data("kkj")
    if cached is not None and (
        cached.get("signals") is not None or cached.get("prefecture_rankings") is not None
    ):
        return {
            "success": True,
            "data": _kkj_fill_defaults(cached),
            "status": "cached",
            "source": "database_cache",
        }
    return {
        "success": True,
        "data": _kkj_empty_payload(),
        "status": "cache_only_empty",
        "source": "database_cache",
    }


def _thehackernews(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_thehackernews_trends_from_cache() or [], limit)


def _ipa(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_ipa_trends_from_cache() or [], limit)


def _jpcert(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_jpcert_trends_from_cache() or [], limit)


def _hackernoon(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_hackernoon_trends_from_cache() or [], limit)


def _zenn(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_zenn_trends_from_cache() or [], limit)


def _note(db: TrendsCache, *, category: str = "all", limit: int = 25, **_) -> list:
    return _limit(db.get_note_trends_from_cache(category) or [], limit)


def _ebay(db: TrendsCache, *, category: str = "electronics", limit: int = 25, **_) -> list:
    return _limit(db.get_ebay_trends_from_cache(category) or [], limit)


def _medium(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_medium_trends_from_cache() or [], limit)


def _devto(db: TrendsCache, *, limit: int = 25, **_) -> list:
    return _limit(db.get_devto_trends_from_cache() or [], limit)


def _openalex(
    db: TrendsCache,
    *,
    category: str = "trending",
    region: str | None = None,
    limit: int = 25,
    **_,
) -> list:
    # manager と同じ: region=jp のとき category_jp バケットを読む
    cache_category = f"{category}_jp" if (region or "").lower() == "jp" else category
    return _limit(db.get_openalex_trends_from_cache(category=cache_category) or [], limit)


def _bluesky(db: TrendsCache, *, region: str = "us", limit: int = 25, **_) -> list:
    return _limit(db.get_bluesky_trends_from_cache(region=region) or [], limit)


_READERS: dict[str, Callable[..., Any]] = {
    "google": _google,
    "youtube": _youtube,
    "music": _music,
    "worldnews": _worldnews,
    "podcast": _podcast,
    "rakuten": _rakuten,
    "hatena": _hatena,
    "twitch": _twitch,
    "hackernews": _hackernews,
    "qiita": _qiita,
    "github": _github,
    "appstore": _appstore,
    "nhk": _nhk,
    "prtimes": _prtimes,
    "prtimes_hatena": _prtimes_hatena,
    "globenewswire": _globenewswire,
    "globenewswire_market_reaction": _globenewswire_market_reaction,
    "wikipedia": _wikipedia,
    "producthunt": _producthunt,
    "cnn": _cnn,
    "stock": _stock,
    "crypto": _crypto,
    "movie": _movie,
    "book": _book,
    "cisa_kev": _cisa_kev,
    "estat": _estat,
    "bls": _bls,
    "usaspending": _usaspending,
    "kkj": _kkj,
    "thehackernews": _thehackernews,
    "ipa": _ipa,
    "jpcert": _jpcert,
    "hackernoon": _hackernoon,
    "zenn": _zenn,
    "note": _note,
    "ebay": _ebay,
    "medium": _medium,
    "devto": _devto,
    "openalex": _openalex,
    "bluesky": _bluesky,
}


def _merge_args(manager_key: str, args: tuple, kwargs: dict) -> dict:
    """ルートごとの位置引数を kwargs に寄せる（force_refresh は落とす）。"""
    kw = {k: v for k, v in kwargs.items() if k != "force_refresh"}
    if not args:
        return kw

    if manager_key == "youtube":
        # get_trends(region, ...) / get_rising_trends(region, ...)
        if len(args) >= 1 and "region_code" not in kw and "region" not in kw:
            kw["region_code"] = args[0]
        if len(args) >= 2 and "max_results" not in kw and "limit" not in kw:
            kw["max_results"] = args[1]
    elif manager_key == "music":
        if len(args) >= 1 and "service" not in kw:
            kw["service"] = args[0]
        if len(args) >= 2 and "region" not in kw:
            kw["region"] = args[1]
    elif manager_key == "worldnews":
        if len(args) >= 1 and "country" not in kw:
            kw["country"] = args[0]
        if len(args) >= 2 and "category" not in kw:
            kw["category"] = args[1]
    elif manager_key == "podcast":
        if len(args) >= 1 and "trend_type" not in kw:
            kw["trend_type"] = args[0]
        if len(args) >= 2 and "genre_id" not in kw:
            kw.setdefault("genre_id", args[1])
        if len(args) >= 3 and "region" not in kw:
            kw["region"] = args[2]
        if len(args) >= 4 and "page_size" not in kw:
            kw["page_size"] = args[3]
    elif manager_key == "rakuten":
        if len(args) >= 1 and "genre_id" not in kw:
            kw["genre_id"] = args[0]
    elif manager_key == "hackernews":
        if len(args) >= 1 and "story_type" not in kw:
            kw["story_type"] = args[0]
        if len(args) >= 2 and "limit" not in kw:
            kw["limit"] = args[1]
    elif manager_key == "google":
        if len(args) >= 1 and "region" not in kw:
            kw["region"] = args[0]
    return kw


def read_cached_data(manager_key: str, *args, **kwargs) -> Any:
    reader = _READERS.get(manager_key)
    if not reader:
        logger.warning("cache_serving: unknown manager_key=%s", manager_key)
        return []
    params = _merge_args(manager_key, args, kwargs)
    try:
        return reader(TrendsCache(), **params)
    except Exception as e:
        logger.warning("cache_serving: read failed key=%s err=%s", manager_key, e, exc_info=True)
        return [] if manager_key not in ("usaspending", "kkj") else ({} if manager_key == "usaspending" else None)


def cached_trends_result(manager_key: str, *args, **kwargs) -> dict:
    if manager_key == "kkj":
        return _kkj_cached_result()

    data = read_cached_data(manager_key, *args, **kwargs)
    if manager_key == "usaspending":
        ok = bool(data)
        return {
            "success": True,
            "data": data if data is not None else {},
            "status": "cached" if ok else "cache_only_empty",
            "source": "database_cache",
        }
    has = isinstance(data, list) and len(data) > 0
    return {
        "success": True,
        "data": data if isinstance(data, list) else [],
        "status": "cached" if has else "cache_only_empty",
        "source": "database_cache",
    }


class CacheOnlyManagerProxy:
    """manager 互換の薄いプロキシ。get_trends 等はキャッシュのみ。"""

    def __init__(self, manager_key: str):
        self.manager_key = manager_key
        self.service_name = manager_key

    def get_trends(self, *args, **kwargs):
        # shed 中の force_refresh は外部 API を叩かずキャッシュのみ
        if kwargs.pop("force_refresh", False):
            logger.info(
                "cache_serving: force_refresh ignored during shed (key=%s)",
                self.manager_key,
            )
        return cached_trends_result(self.manager_key, *args, **kwargs)

    def get_rising_trends(self, region_code: str = "JP", max_results: int = 25, force_refresh: bool = False):
        return cached_trends_result(
            "youtube",
            region_code=region_code,
            trend_type="rising",
            max_results=max_results,
        )

    def get_public_sector_signals(self, force_refresh: bool = False, cache_only: bool = True, **kwargs):
        if force_refresh:
            logger.info("cache_serving: force_refresh ignored during shed (key=kkj)")
        return _kkj_cached_result()

    def get_genres(self):
        return []

    def get_available_categories(self):
        return []


def resolve_manager_for_request(manager_key: str, managers: dict | None) -> Any:
    """実 manager があればそれ、なければ CacheOnlyManagerProxy。"""
    if managers:
        m = managers.get(manager_key)
        if m is not None:
            return m
    return CacheOnlyManagerProxy(manager_key)
