"""
SSR（Server-Side Rendering）用トレンドデータ取得モジュール
ページ初回表示時にHTMLに埋め込むため、キャッシュからデータを取得する
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional
from utils.logger_config import get_logger

logger = get_logger(__name__)

# 全部入りタブでSSRするソース一覧（表示順・APIパラメータ）
SSR_SOURCES = [
    {'key': 'nhk', 'manager_key': 'nhk', 'fetcher': lambda m: m.get_trends(limit=5, force_refresh=False)},
    {'key': 'news', 'manager_key': 'worldnews', 'fetcher': lambda m: m.get_trends(country='jp', category='general', force_refresh=False)},
    {'key': 'wikipedia', 'manager_key': 'wikipedia', 'fetcher': lambda m: m.get_trends(lang='ja', limit=5, force_refresh=False)},
    {'key': 'google', 'manager_key': 'google', 'fetcher': lambda m: m.get_trends(region='JP', force_refresh=False)},
    {'key': 'youtube', 'manager_key': 'youtube', 'fetcher': lambda m: m.get_trends(region_code='JP', max_results=5, force_refresh=False)},
]

# US全部入りタブでSSRするソース一覧
SSR_SOURCES_US = [
    {'key': 'cnn', 'manager_key': 'cnn', 'fetcher': lambda m: m.get_trends(limit=5, force_refresh=False)},
    {'key': 'worldnews', 'manager_key': 'worldnews', 'fetcher': lambda m: m.get_trends(country='us', category=None, page_size=5, force_refresh=False)},
    {'key': 'wikipedia', 'manager_key': 'wikipedia', 'fetcher': lambda m: m.get_trends(lang='en', limit=5, force_refresh=False)},
    {'key': 'google', 'manager_key': 'google', 'fetcher': lambda m: m.get_trends(region='US', force_refresh=False)},
    {'key': 'youtube', 'manager_key': 'youtube', 'fetcher': lambda m: m.get_trends(region_code='US', max_results=5, force_refresh=False)},
]


def _fetch_one(managers: dict, config: dict) -> tuple:
    """1ソースのデータを取得（キャッシュ優先）"""
    key = config['key']
    manager_key = config['manager_key']
    fetcher = config['fetcher']
    manager = managers.get(manager_key)
    if not manager:
        return key, None
    try:
        result = fetcher(manager)
        if isinstance(result, dict) and result.get('success', True) and result.get('data'):
            return key, result
        if isinstance(result, list) and len(result) > 0:
            return key, {'success': True, 'data': result[:5]}
    except Exception as e:
        logger.debug(f"SSR fetch {key} failed: {e}")
    return key, None


def _sort_and_limit(key: str, data: list) -> list:
    """ソースごとのソート・件数制限"""
    if not data:
        return []
    limit = 5
    if key == 'google':
        return sorted(data, key=lambda x: (x.get('score') or x.get('popularity') or 0), reverse=True)[:limit]
    if key == 'youtube':
        return sorted(data, key=lambda x: x.get('view_count') or 0, reverse=True)[:limit]
    return data[:limit]


def fetch_ssr_trends(managers: dict) -> Dict[str, List[dict]]:
    """
    全部入りタブ用のトレンドデータを並列取得（キャッシュのみ、外部APIは呼ばない）
    
    Args:
        managers: app.config['TREND_MANAGERS']
    
    Returns:
        { 'nhk': [item,...], 'news': [...], ... }
        各リストは最大5件
    """
    out = {}
    if not managers:
        return out
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_one, managers, cfg): cfg for cfg in SSR_SOURCES}
        for future in as_completed(futures):
            try:
                key, result = future.result()
                if result and result.get('data'):
                    data = result['data'] if isinstance(result['data'], list) else []
                    out[key] = _sort_and_limit(key, data)
            except Exception as e:
                logger.debug(f"SSR future error: {e}")
    
    return out


def build_ssr_itemlist_json_ld(
    ssr: Optional[Dict[str, List[dict]]], *, variant: str
) -> Optional[Dict[str, Any]]:
    """
    トレンドのサーバースナップショットを schema.org ItemList として返す（本文との二重表示を避けつつ HTML に含める）。
    variant: 'jp' | 'us'
    """
    if not ssr:
        return None
    if variant == "jp":
        specs = [
            ("google", "Google Trends"),
            ("news", "ニュース"),
            ("youtube", "YouTube"),
        ]
        list_name = "主要トレンド（サーバー側スナップショット）"
    elif variant == "us":
        specs = [
            ("google", "Google Trends"),
            ("cnn", "CNN"),
            ("youtube", "YouTube"),
        ]
        list_name = "Trend highlights (server snapshot)"
    else:
        return None

    elements: List[Dict[str, Any]] = []
    position = 1
    max_items = 24
    for key, label in specs:
        for item in ssr.get(key) or []:
            if len(elements) >= max_items:
                break
            text = (item.get("keyword") or item.get("title") or "").strip()
            if not text:
                continue
            name = f"{label}: {text}"
            if len(name) > 500:
                name = name[:497] + "..."
            elements.append(
                {
                    "@type": "ListItem",
                    "position": position,
                    "name": name,
                }
            )
            position += 1
        if len(elements) >= max_items:
            break

    if not elements:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": list_name,
        "numberOfItems": len(elements),
        "itemListElement": elements,
    }


def fetch_ssr_trends_us(managers: dict) -> Dict[str, List[dict]]:
    """
    US全部入りタブ用のトレンドデータを並列取得（キャッシュのみ、外部APIは呼ばない）
    
    Args:
        managers: app.config['TREND_MANAGERS']
    
    Returns:
        { 'cnn': [...], 'worldnews': [...], 'wikipedia': [...], 'google': [...], 'youtube': [...] }
        各リストは最大5件
    """
    out = {}
    if not managers:
        return out
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_one, managers, cfg): cfg for cfg in SSR_SOURCES_US}
        for future in as_completed(futures):
            try:
                key, result = future.result()
                if result and result.get('data'):
                    data = result['data'] if isinstance(result['data'], list) else []
                    out[key] = _sort_and_limit(key, data)
            except Exception as e:
                logger.debug(f"SSR US future error: {e}")
    
    return out
