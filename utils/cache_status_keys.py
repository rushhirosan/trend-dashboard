"""cache_status テーブル用キー: refresh 結果・鮮度表示の JP/US 分離。"""

from __future__ import annotations

from typing import Any


def map_refresh_result_key_to_cache_keys(result_key: str) -> str | list[str] | None:
    """refresh_all_trends の結果キー（例: google_JP）→ cache_status.cache_key。"""
    if "_" not in result_key:
        return None

    parts = result_key.rsplit("_", 1)
    if len(parts) != 2:
        return None

    key, region = parts
    if region not in ("JP", "US"):
        return None

    if key == "stock":
        return f"stock_trends_{region}"
    if key == "book":
        return f"book_trends_{region}"
    if key == "movie":
        return f"movie_trends_{region}"
    if key == "appstore":
        return f"appstore_trends_{region}"
    if key == "ebay":
        return "ebay_trends"
    if key == "note":
        return [
            "note_trends_all",
            "note_trends_tech",
            "note_trends_business",
            "note_trends_lifestyle",
            "note_trends_entertainment",
        ]
    if key == "wikipedia":
        return f"wikipedia_trends_{'ja' if region == 'JP' else 'en'}"
    if key == "music":
        return f"music_trends_{region}"
    if key == "bluesky":
        return "bluesky_trends_jp" if region == "JP" else "bluesky_trends"
    if key == "openalex":
        cats = ("trending", "ai", "nlp", "climate", "biotech", "quantum", "medical")
        if region == "JP":
            return [f"openalex_trends_{c}_jp" for c in cats]
        return [f"openalex_trends_{c}" for c in cats]
    if key == "worldnews":
        return f"worldnews_trends_{region.lower()}"

    return f"{key}_trends_{region}"


# data-freshness の base cache_key → 地域 suffix 付きキーを優先（旧キーはフォールバック）
_REGION_SUFFIX_BASE_KEYS = frozenset(
    {
        "google_trends",
        "youtube_trends",
        "podcast_trends",
        "crypto_trends",
        "github_trends",
        "hatena_trends",
        "qiita_trends",
        "nhk_trends",
        "prtimes_trends",
        "prtimes_hatena_trends",
        "zenn_trends",
        "ipa_trends",
        "jpcert_trends",
        "rakuten_trends",
        "twitch_trends",
        "estat_trends",
        "kkj_trends",
    }
)


def resolve_cache_status_key(base_key: str, **kwargs: Any) -> str:
    """保存時 cache_status 用。region / country / market から JP/US キーへ。"""
    region = kwargs.get("region") or kwargs.get("region_code") or kwargs.get("market")
    if isinstance(region, str):
        r = region.upper()
        if r in ("JP", "US"):
            if base_key == "worldnews_trends":
                return f"worldnews_trends_{r.lower()}"
            if base_key.endswith(f"_{r}") or base_key.endswith("_ja") or base_key.endswith("_en"):
                return base_key
            if base_key in _REGION_SUFFIX_BASE_KEYS or base_key.endswith("_trends"):
                if base_key in ("bluesky_trends", "bluesky_trends_jp"):
                    return "bluesky_trends_jp" if r == "JP" else "bluesky_trends"
                if base_key.startswith("openalex_trends_"):
                    return base_key
                if base_key in ("movie_trends", "book_trends", "appstore_trends", "stock_trends", "music_trends"):
                    return f"{base_key}_{r}"
                if base_key.endswith("_trends") and not base_key.endswith(f"_trends_{r}"):
                    return f"{base_key}_{r}"
    country = kwargs.get("country")
    if country and str(country).lower() in ("jp", "us"):
        c = str(country).lower()
        if base_key == "worldnews_trends":
            return f"worldnews_trends_{c}"
    return base_key


def freshness_lookup_keys(base_cache_key: str, country: str) -> list[str]:
    """鮮度 API: 試行順（地域キー → 旧共有キー）。"""
    country = (country or "JP").upper()
    keys: list[str] = []

    if base_cache_key == "worldnews_trends":
        keys.append(f"worldnews_trends_{country.lower()}")
    elif base_cache_key == "bluesky_trends":
        keys.append("bluesky_trends_jp" if country == "JP" else "bluesky_trends")
    elif base_cache_key == "openalex_trends_trending":
        keys.append(
            "openalex_trends_trending_jp" if country == "JP" else "openalex_trends_trending"
        )
    elif base_cache_key in ("movie_trends", "book_trends", "appstore_trends", "stock_trends", "music_trends"):
        keys.append(f"{base_cache_key}_{country}")
    elif base_cache_key.endswith("_trends") and base_cache_key in _REGION_SUFFIX_BASE_KEYS:
        keys.append(f"{base_cache_key}_{country}")

    if base_cache_key not in keys:
        keys.append(base_cache_key)
    return keys


def region_refresh_stats(results: dict) -> dict[str, dict[str, int | bool]]:
    """結果 dict から JP/US 別成功数を集計。"""

    def _bucket(suffix: str) -> dict:
        subset = {k: v for k, v in results.items() if k.endswith(f"_{suffix}")}
        total = len(subset)
        success = sum(1 for v in subset.values() if v.get("success"))
        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "ok": total > 0 and success == total,
        }

    return {"JP": _bucket("JP"), "US": _bucket("US")}
