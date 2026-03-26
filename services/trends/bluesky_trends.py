"""
Bluesky トレンドマネージャー

Bluesky AT Protocol の公開API（認証不要）を使用
- What's Hot フィード: ネットワーク全体のトレンド投稿（US向け）
- Japanese Super Hot: 100いいね以上の日本語投稿（日本向け）
- ドキュメント: https://docs.bsky.app/docs/api/app-bsky-feed-get-feed
"""

import requests
from typing import Dict, List, Any, Optional

from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# Bluesky フィードURI
WHATS_HOT_FEED_URI = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot"
# 日本語向け: 100いいね以上の日本語投稿（Japanese Super Hot by コミュニティ）
JAPANESE_SUPER_HOT_URI = "at://did:plc:ilxxgyz7oz7mysber4omeqrg/app.bsky.feed.generator/aaahn3ic3dtyi"
BASE_URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed"


class BlueskyTrendsManager(BaseTrendsManager):
    """Blueskyトレンド管理クラス"""

    def __init__(self):
        """初期化"""
        super().__init__(service_name="bluesky", max_requests=30, window_seconds=60)
        logger.info("Bluesky Trends Manager初期化:")
        logger.info(f"  API: {BASE_URL}")
        logger.info("  認証: 不要（公開API）")

    def _get_cache_key(self, *args, **kwargs) -> str:
        """キャッシュキーを返す（region=jpの場合は別キャッシュ）"""
        region = kwargs.get("region")
        return "bluesky_trends_jp" if region == "jp" else "bluesky_trends"

    def _get_from_cache(self, *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """キャッシュからデータを取得"""
        region = kwargs.get("region")
        try:
            cached_data = self.db.get_bluesky_trends_from_cache(region=region)
            if cached_data and len(cached_data) > 0:
                logger.info(f"✅ Bluesky: キャッシュから{len(cached_data)}件のデータを取得")
                return cached_data
            return None
        except Exception as e:
            logger.error(f"❌ Bluesky: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data: List[Dict[str, Any]], *args, **kwargs) -> bool:
        """キャッシュにデータを保存"""
        region = kwargs.get("region")
        success = self.db.save_bluesky_trends_to_cache(data, region=region)
        if success:
            logger.info(f"✅ Bluesky: キャッシュに保存完了 ({len(data)}件)")
            return True
        # ここに来る場合はDB層が False を返したケース。詳細付きで例外化して Base 側アラートに載せる。
        raise RuntimeError(
            f"bluesky cache save returned False (region={region or 'us'}). "
            "See database_config save_bluesky_trends_to_cache logs for root cause."
        )

    def _clear_cache(self, *args, **kwargs) -> bool:
        """キャッシュをクリア"""
        region = kwargs.get("region")
        try:
            return self.db.clear_bluesky_trends_cache(region=region)
        except Exception as e:
            logger.error(f"❌ Bluesky キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key: str, data_count: int, *args, **kwargs) -> bool:
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Bluesky: cache_status更新エラー: {e}")
            return False

    @staticmethod
    def _extract_post_rkey(uri: str) -> str:
        """post URIからrkeyを抽出（例: at://.../app.bsky.feed.post/3mhkhpcdygk2u -> 3mhkhpcdygk2u）"""
        if not uri:
            return ""
        parts = uri.split("/")
        return parts[-1] if parts else ""

    def _parse_feed_item(self, item: dict, rank: int) -> Optional[Dict[str, Any]]:
        """フィードアイテムをパース"""
        try:
            post = item.get("post", {})
            if not post:
                return None

            author = post.get("author", {})
            record = post.get("record", {})
            handle = author.get("handle", "")
            display_name = author.get("displayName") or handle
            text = record.get("text", "") or ""
            uri = post.get("uri", "")
            rkey = self._extract_post_rkey(uri)

            # 投稿URL: https://bsky.app/profile/{handle}/post/{rkey}
            url = f"https://bsky.app/profile/{handle}/post/{rkey}" if handle and rkey else ""

            like_count = post.get("likeCount", 0)
            reply_count = post.get("replyCount", 0)
            repost_count = post.get("repostCount", 0)
            created_at = record.get("createdAt", "")

            # テーブル表示用: タイトルは本文の先頭100文字（改行はスペースに）
            title = (text[:100] + "…") if len(text) > 100 else text
            title = title.replace("\n", " ").strip() or "(メディア投稿)"

            return {
                "rank": rank,
                "post_uri": uri,
                "post_id": rkey,
                "title": title,
                "text": text,
                "user_handle": handle,
                "user_display_name": display_name,
                "like_count": like_count,
                "reply_count": reply_count,
                "repost_count": repost_count,
                "url": url,
                "created_at": created_at,
                "source": "Bluesky",
            }
        except Exception as e:
            logger.warning(f"⚠️ Bluesky 投稿パースエラー: {e}")
            return None

    def _fetch_trends(self, limit: int = 25, *args, **kwargs) -> Dict[str, Any]:
        """Bluesky APIからトレンドデータを取得
        region=jp: Japanese Super Hot（100いいね以上の日本語投稿）
        region=us/未指定: What's Hot（グローバルトレンド）
        """
        try:
            self.rate_limiter.wait_if_needed()

            region = kwargs.get("region")
            feed_uri = JAPANESE_SUPER_HOT_URI if region == "jp" else WHATS_HOT_FEED_URI
            if region == "jp":
                logger.info("Bluesky: Japanese Super Hot フィードを使用（日本語投稿）")

            params = {
                "feed": feed_uri,
                "limit": min(limit, 100),
            }

            headers = {"Accept": "application/json"}
            response = requests.get(BASE_URL, params=params, headers=headers, timeout=15)
            response.raise_for_status()

            data = response.json()
            feed_items = data.get("feed", [])

            if not feed_items:
                logger.warning("⚠️ Bluesky API: フィードが空でした")
                return {
                    "success": True,
                    "data": [],
                    "status": "no_posts",
                    "source": "Bluesky API",
                }

            formatted_data = []
            for i, item in enumerate(feed_items[:limit], 1):
                parsed = self._parse_feed_item(item, rank=i)
                if parsed:
                    formatted_data.append(parsed)

            logger.info(f"✅ Bluesky: {len(formatted_data)}件のトレンド投稿を取得しました")

            return {
                "success": True,
                "data": formatted_data,
                "status": "api_fetched",
                "source": "Bluesky API",
            }

        except requests.exceptions.Timeout:
            logger.error("❌ Bluesky API タイムアウトエラー", exc_info=True)
            return {"success": False, "error": "Bluesky API タイムアウト", "data": []}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Bluesky API リクエストエラー: {e}", exc_info=True)
            return {"success": False, "error": f"Bluesky APIエラー: {str(e)}", "data": []}
        except Exception as e:
            logger.error(f"❌ Bluesky API エラー: {e}", exc_info=True)
            return {"success": False, "error": str(e), "data": []}

    def get_trends(
        self,
        limit: int = 25,
        force_refresh: bool = False,
        region: str = None,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """Blueskyトレンドを取得（キャッシュ優先）
        region=jp: Japanese Super Hot（100いいね以上の日本語投稿）
        region=us/未指定: What's Hot（グローバルトレンド）
        """
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key="like_count",
            sort_reverse=True,
            region=region,
        )
