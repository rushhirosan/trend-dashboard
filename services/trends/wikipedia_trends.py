"""
Wikipedia Featured content API (most read articles) を使用して
人気記事トレンドを取得・管理するクラス
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# Wikimedia API 推奨: User-Agent にアプリ名と連絡先を含める
WIKIPEDIA_USER_AGENT = os.getenv(
    "WIKIPEDIA_USER_AGENT",
    "TrendDashboard/1.0 (https://github.com/trend-dashboard; contact@example.com)"
)


class WikipediaTrendsManager(BaseTrendsManager):
    """Wikipedia の「最も読まれた記事」を取得するマネージャー"""

    BASE_URL = "https://api.wikimedia.org/feed/v1/wikipedia"

    def __init__(self):
        super().__init__(service_name="wikipedia", max_requests=10, window_seconds=60)
        self.session = requests.Session()
        headers = {"User-Agent": WIKIPEDIA_USER_AGENT}
        token = os.getenv("WIKIPEDIA_ACCESS_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.info("Wikipedia Trends Manager: WIKIPEDIA_ACCESS_TOKEN を使用します")
        else:
            logger.info("Wikipedia Trends Manager: トークン未設定（User-Agent のみ）")
        self.session.headers.update(headers)
        logger.info("Wikipedia Trends Manager 初期化 (Featured content API mostread)")

    def _get_cache_key(self, lang: str = "ja", **kwargs) -> str:
        return f"wikipedia_trends_{lang}"

    def _get_from_cache(self, lang: str = "ja", **kwargs) -> Optional[List[Dict[str, Any]]]:
        try:
            return self.db.get_wikipedia_trends_from_cache(lang=lang)
        except Exception as e:
            logger.error(f"Wikipedia キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data: List[Dict[str, Any]], lang: str = "ja", **kwargs) -> bool:
        try:
            return self.db.save_wikipedia_trends_to_cache(data, lang=lang)
        except Exception as e:
            logger.error(f"Wikipedia キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, lang: str = "ja", **kwargs) -> bool:
        try:
            return self.db.clear_wikipedia_trends_cache(lang=lang)
        except Exception as e:
            logger.error(f"Wikipedia キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(
        self, cache_key: str, data_count: int, lang: str = "ja", **kwargs
    ) -> bool:
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"Wikipedia cache_status 更新エラー: {e}")
            return False

    def _parse_mostread_articles(self, articles: List[Dict], lang: str) -> List[Dict[str, Any]]:
        """API の mostread.articles をダッシュボード用の形式に変換"""
        result = []
        for i, art in enumerate(articles):
            if not isinstance(art, dict):
                continue
            # content_urls.desktop.page または mobile.page
            urls = art.get("content_urls") or {}
            desktop = urls.get("desktop") or {}
            page_url = desktop.get("page") or (urls.get("mobile") or {}).get("page") or ""
            # タイトル: titles.normalized または display または title (deprecated)
            titles = art.get("titles") or {}
            title = (
                titles.get("normalized")
                or titles.get("display")
                or art.get("title", "").replace("_", " ")
            )
            if not title and art.get("title"):
                title = str(art["title"]).replace("_", " ")
            rank = art.get("rank", i + 1)
            views = art.get("views", 0)
            description = (art.get("extract") or "")[:500] if art.get("extract") else ""
            result.append({
                "title": title or "Untitled",
                "url": page_url or "",
                "rank": rank,
                "views": views,
                "description": description,
            })
        return result

    def _fetch_trends(
        self,
        lang: str = "ja",
        limit: int = 25,
        date: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Featured content API で指定日の most read を取得。
        mostread は「前日」のデータなので、date は表示したい日（前日分を取るなら date=昨日）。
        """
        if not date:
            date = datetime.utcnow() - timedelta(days=1)
        yyyy = date.strftime("%Y")
        mm = date.strftime("%m")
        dd = date.strftime("%d")
        url = f"{self.BASE_URL}/{lang}/featured/{yyyy}/{mm}/{dd}"

        try:
            self.rate_limiter.wait_if_needed()
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            logger.error("Wikipedia Featured API タイムアウト", exc_info=True)
            return {"success": False, "error": "API timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Wikipedia Featured API リクエストエラー: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
        except ValueError as e:
            logger.error(f"Wikipedia API JSON パースエラー: {e}", exc_info=True)
            return {"success": False, "error": "Invalid JSON response"}

        mostread = data.get("mostread") or {}
        articles = mostread.get("articles") or []
        if not articles:
            logger.warning("Wikipedia mostread.articles が空です")
            return {
                "success": True,
                "data": [],
                "status": "api_fetched",
                "source": "wikipedia_featured",
                "total_count": 0,
            }

        formatted = self._parse_mostread_articles(articles, lang)
        # rank を 1 から振り直し
        for i, item in enumerate(formatted[:limit], 1):
            item["rank"] = i

        logger.info(f"Wikipedia ({lang}): most read {len(formatted)} 件取得")
        return {
            "success": True,
            "data": formatted[:limit],
            "status": "api_fetched",
            "source": "wikipedia_featured",
            "total_count": len(formatted),
        }

    def get_trends(
        self,
        lang: str = "ja",
        limit: int = 25,
        force_refresh: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        指定言語の Wikipedia 人気記事を取得。
        lang: 'ja' (日本), 'en' (英語/US) など。
        """
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key="rank",
            sort_reverse=False,
            lang=lang,
            **kwargs
        )
