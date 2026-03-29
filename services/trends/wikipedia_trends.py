"""
Wikipedia Featured content API (most read articles) を使用して
人気記事トレンドを取得・管理するクラス
"""

import os
import time
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

    # API が一時的に0件でも DB に残っている直近キャッシュを応答に使う
    use_stale_cache_when_api_empty = True

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
            # ベースのアラートでエラー詳細を送れるよう再送出
            raise

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

    # Connection reset by peer 等の一時的エラーでリトライする例外
    _RETRIABLE_EXCEPTIONS = (
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
    )

    def _fetch_one_day(self, lang: str, date: datetime, timeout_sec: int = 30) -> Dict[str, Any]:
        """指定日1日分の API を叩き、articles リストを返す。失敗時は error を返す。
        一時的な接続エラー（Connection reset by peer 等）の場合は最大3回リトライする。
        """
        yyyy = date.strftime("%Y")
        mm = date.strftime("%m")
        dd = date.strftime("%d")
        url = f"{self.BASE_URL}/{lang}/featured/{yyyy}/{mm}/{dd}"
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait_if_needed()
                resp = self.session.get(url, timeout=timeout_sec)
                resp.raise_for_status()
                data = resp.json()
                mostread = data.get("mostread") or {}
                articles = mostread.get("articles") or []
                return {"articles": articles, "yyyy": yyyy, "mm": mm, "dd": dd}
            except requests.exceptions.Timeout:
                return {"error": "timeout"}
            except self._RETRIABLE_EXCEPTIONS as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_sec = 2 ** (attempt + 1)
                    logger.warning(
                        "Wikipedia API 接続エラー (attempt %d/%d): %s - %s秒後にリトライ",
                        attempt + 1, max_retries, e, wait_sec,
                    )
                    time.sleep(wait_sec)
                else:
                    logger.error("Wikipedia API 接続エラー (全リトライ失敗): %s", e)
                    return {"error": str(e)}
            except requests.exceptions.RequestException as e:
                return {"error": str(e)}
            except ValueError:
                return {"error": "Invalid JSON response"}

        return {"error": str(last_error) if last_error else "Unknown error"}

    def _fetch_trends(
        self,
        lang: str = "ja",
        limit: int = 25,
        date: Optional[datetime] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Featured content API で指定日の most read を取得。
        指定日にデータがなければ最大7日さかのぼってフォールバックする。
        """
        if not date:
            date = datetime.utcnow() - timedelta(days=1)
        timeout_sec = 30
        max_fallback_days = 7

        for day_offset in range(max_fallback_days):
            try_date = date - timedelta(days=day_offset)
            result = self._fetch_one_day(lang, try_date, timeout_sec=timeout_sec)
            if "error" in result:
                if day_offset == 0:
                    logger.error("Wikipedia Featured API エラー (date=%s): %s", try_date, result["error"])
                    return {"success": False, "error": result["error"]}
                continue
            articles = result.get("articles") or []
            if not articles:
                logger.debug(
                    "Wikipedia mostread が空 (lang=%s, date=%s/%s/%s)、前日を試します.",
                    lang, result["yyyy"], result["mm"], result["dd"],
                )
                continue
            formatted = self._parse_mostread_articles(articles, lang)
            for i, item in enumerate(formatted[:limit], 1):
                item["rank"] = i
            logger.info(
                "Wikipedia (%s): most read %d 件取得 (date=%s/%s/%s)",
                lang, len(formatted), result["yyyy"], result["mm"], result["dd"],
            )
            return {
                "success": True,
                "data": formatted[:limit],
                "status": "api_fetched",
                "source": "wikipedia_featured",
                "total_count": len(formatted),
            }

        logger.warning(
            "Wikipedia: %d 日分試しましたが most read が取得できませんでした (lang=%s)",
            max_fallback_days, lang,
        )
        return {
            "success": True,
            "data": [],
            "status": "api_fetched",
            "source": "wikipedia_featured",
            "total_count": 0,
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
