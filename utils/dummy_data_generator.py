"""
ダミーデータ生成ユーティリティ
ローカル開発環境用のダミーデータ（Lorem ipsum）を生成する機能を提供
"""

import random
from datetime import datetime
from typing import List, Dict, Any


# Lorem ipsumテキストのサンプル
LOREM_IPSUM_WORDS = [
    "Lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
    "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
    "magna", "aliqua", "Ut", "enim", "ad", "minim", "veniam", "quis", "nostrud",
    "exercitation", "ullamco", "laboris", "nisi", "ut", "aliquip", "ex", "ea",
    "commodo", "consequat", "Duis", "aute", "irure", "dolor", "in", "reprehenderit",
    "in", "voluptate", "velit", "esse", "cillum", "dolore", "eu", "fugiat", "nulla",
    "pariatur", "Excepteur", "sint", "occaecat", "cupidatat", "non", "proident",
    "sunt", "in", "culpa", "qui", "officia", "deserunt", "mollit", "anim", "id",
    "est", "laborum"
]


def generate_lorem_text(min_words: int = 5, max_words: int = 20) -> str:
    """Lorem ipsumテキストを生成するヘルパー関数"""
    word_count = random.randint(min_words, max_words)
    words = random.sample(LOREM_IPSUM_WORDS, min(word_count, len(LOREM_IPSUM_WORDS)))
    # 最初の単語を大文字に
    if words:
        words[0] = words[0].capitalize()
    return " ".join(words) + "."


def generate_dummy_trends_data(service_name: str, limit: int = 25, *args, **kwargs) -> List[Dict[str, Any]]:
    """ダミートレンドデータを生成する（デフォルト実装）
    
    各マネージャーで必要に応じてカスタマイズ可能
    """
    dummy_data: List[Dict[str, Any]] = []
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "rank": i,
            "title": generate_lorem_text(3, 8),
            "url": "#",
            "description": generate_lorem_text(10, 30),
            "source": service_name,
        }
        dummy_data.append(item)
    
    return dummy_data


def generate_dummy_stock_data(market: str = "US", limit: int = 25) -> List[Dict[str, Any]]:
    """株価トレンド用のダミーデータを生成する（ローカルキャッシュ用）
    
    実株価がローカルに保存されないよう、symbol/name/価格はすべてダミー。
    フロントの表示形式（symbol, name, current_price, change_percent 等）に準拠。
    
    Args:
        market: 'JP' または 'US'
        limit: 件数
    
    Returns:
        株価キャッシュと同じ形式のリスト
    """
    dummy_data: List[Dict[str, Any]] = []
    is_jp = (market or "US").upper() == "JP"
    suffix = ".T" if is_jp else ""
    
    for i in range(1, limit + 1):
        previous_price = random.uniform(1000.0, 50000.0)
        change_pct = random.uniform(-2.5, 2.5)
        change = previous_price * (change_pct / 100.0)
        current_price = previous_price + change
        volume = random.randint(100_000, 10_000_000)
        
        symbol = f"DMY{i}{suffix}"
        name = generate_lorem_text(2, 5).rstrip(".")
        
        item: Dict[str, Any] = {
            "rank": i,
            "symbol": symbol,
            "name": name,
            "current_price": round(current_price, 2),
            "previous_price": round(previous_price, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 2),
            "volume": volume,
            "market_cap": 0,
            "market": market or "US",
            "updated_at": datetime.now().isoformat(),
        }
        dummy_data.append(item)
    
    return dummy_data


def generate_dummy_movie_data(country: str = "JP", limit: int = 25) -> List[Dict[str, Any]]:
    """映画トレンド用のダミーデータを生成（movie_trends_cache スキーマ互換）
    
    movie_id は負の整数でユニークにし、実データと衝突しないようにする。
    """
    dummy_data: List[Dict[str, Any]] = []
    now = datetime.now().isoformat()
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "id": -i,
            "movie_id": -i,
            "title": generate_lorem_text(2, 6).rstrip("."),
            "original_title": generate_lorem_text(2, 6).rstrip("."),
            "overview": generate_lorem_text(8, 20),
            "popularity": round(random.uniform(1.0, 50.0), 2),
            "vote_average": round(random.uniform(3.0, 9.0), 1),
            "vote_count": random.randint(10, 5000),
            "release_date": "2024-01-01",
            "poster_path": "",
            "backdrop_path": "",
            "poster_url": "",
            "backdrop_url": "",
            "item_url": "#",
            "amazon_link": "",
            "rank": i,
            "updated_at": now,
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_book_data(country: str = "JP", limit: int = 25) -> List[Dict[str, Any]]:
    """書籍トレンド用のダミーデータを生成（book_trends_cache スキーマ互換）"""
    dummy_data: List[Dict[str, Any]] = []
    now = datetime.now().isoformat()
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "id": f"dummy_book_{i}",
            "isbn": "",
            "title": generate_lorem_text(2, 6).rstrip("."),
            "subtitle": "",
            "author": generate_lorem_text(1, 3).rstrip("."),
            "authors": [],
            "publisher": "Example Press",
            "price": random.randint(500, 3000),
            "sales": 0,
            "published_date": "2024-01-01",
            "release_date": "",
            "description": generate_lorem_text(10, 25),
            "page_count": random.randint(100, 400),
            "categories": [],
            "average_rating": round(random.uniform(3.0, 5.0), 1),
            "ratings_count": random.randint(0, 500),
            "language": "ja" if country == "JP" else "en",
            "item_url": "#",
            "affiliate_url": "",
            "preview_link": "",
            "info_link": "",
            "buy_link": "",
            "image_url": "",
            "thumbnail": "",
            "small_thumbnail": "",
            "medium": "",
            "large": "",
            "rank": i,
            "updated_at": now,
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_worldnews_data(country: str = "jp", limit: int = 25) -> List[Dict[str, Any]]:
    """World News 用のダミーデータを生成（worldnews_trends_cache スキーマ互換）"""
    dummy_data: List[Dict[str, Any]] = []
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "article_id": f"dummy_news_{i}",
            "title": generate_lorem_text(3, 10).rstrip("."),
            "source": "Example News",
            "published_at": datetime.now().isoformat(),
            "category": "general",
            "country": country.lower(),
            "url": "#",
            "description": generate_lorem_text(10, 30),
            "image_url": "",
            "rank": i,
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_ebay_data(category: str = "fashion", limit: int = 25) -> List[Dict[str, Any]]:
    """eBay Popular/Trending用のダミーデータを生成（ebay_trends_cache スキーマ互換）"""
    dummy_data: List[Dict[str, Any]] = []
    now = datetime.now().isoformat()
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "rank": i,
            "title": generate_lorem_text(2, 8).rstrip("."),
            "url": f"https://www.ebay.com/itm/dummy_{i}",
            "item_id": f"dummy_ebay_{i}",
            "price": round(random.uniform(9.99, 299.99), 2),
            "currency": "USD",
            "image_url": "",
            "condition": "New",
            "seller": "Example Seller",
            "shipping": "0",
            "category": category,
            "published_date": now,
            "source": "eBay Popular/Trending",
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_estat_data(limit: int = 6) -> List[Dict[str, Any]]:
    """e-Stat（景気・行政指標）用のダミーデータを生成（indicator_id, name_ja, series 形式）"""
    indicators = [
        ("cpi", "消費者物価指数（総合・前年同月比）", "前年同月=100", "102.1", "202602"),
        ("job_ratio", "有効求人倍率", "倍", "1.31", "202601"),
        ("housing_starts", "住宅着工", "棟", "45230", "202601"),
        ("unemployment", "完全失業率", "%", "2.4", "202601"),
        ("real_wages", "実質賃金指数", "前年同月比", "97.5", "202512"),
        ("retail_sales", "小売業販売額", "億円", "14821", "202601"),
    ]
    dummy_data: List[Dict[str, Any]] = []
    for i, (ind_id, name_ja, unit, val, period) in enumerate(indicators[:limit]):
        item: Dict[str, Any] = {
            "indicator_id": ind_id,
            "name_ja": name_ja,
            "unit": unit,
            "series": [{"period": period, "value": val, "unit": unit}],
            "updated_at": period,
            "stats_data_id": None,
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_bls_data(limit: int = 8) -> List[Dict[str, Any]]:
    """BLS（米国労働統計）用のダミーデータを生成（indicator_id, name_en, series 形式）"""
    indicators = [
        ("cpi", "CPI (All Items, SA)", "1982-84=100", "314.2", "202601"),
        ("unemployment", "Unemployment Rate", "%", "3.9", "202601"),
        ("employment", "Total Nonfarm Employment", "thousands", "159526", "202601"),
        ("jolts_openings", "JOLTS Job Openings", "thousands", "9125", "202512"),
        ("jolts_hires", "JOLTS Hires", "thousands", "5923", "202512"),
        ("jolts_quits", "JOLTS Quits", "thousands", "3521", "202512"),
        ("eci", "Employment Cost Index (Wages)", "index", "158.2", "202510"),
        ("construction_emp", "Construction Employment", "thousands", "8275", "202601"),
    ]
    dummy_data: List[Dict[str, Any]] = []
    for i, (ind_id, name_en, unit, val, period) in enumerate(indicators[:limit]):
        item: Dict[str, Any] = {
            "indicator_id": ind_id,
            "name_en": name_en,
            "unit": unit,
            "series": [{"period": period, "value": val, "unit": unit}],
            "updated_at": period,
            "series_id": f"BLS_{ind_id}",
        }
        dummy_data.append(item)
    return dummy_data


def generate_dummy_rakuten_data(limit: int = 25, genre_id: str = "all") -> List[Dict[str, Any]]:
    """楽天トレンド用のダミーデータを生成（rakuten_trends_cache スキーマ互換）"""
    dummy_data: List[Dict[str, Any]] = []
    scope = genre_id or "all"
    for i in range(1, limit + 1):
        item: Dict[str, Any] = {
            "item_id": f"dummy_rakuten_{i}",
            "genre_id": scope,
            "title": generate_lorem_text(2, 8).rstrip("."),
            "price": random.randint(100, 10000),
            "category": scope,
            "review_count": random.randint(0, 200),
            "review_average": round(random.uniform(3.0, 5.0), 1),
            "image_url": "",
            "url": "#",
            "shop_name": "Example Shop",
            "sales_rank": "",
            "sales_count": random.randint(0, 500),
            "rank": i,
            "region": "JP",
        }
        dummy_data.append(item)
    return dummy_data

