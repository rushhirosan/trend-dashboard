"""
音楽トレンド取得。
Apple Music RSS（認証・課金不要）を利用。
https://rss.applemarketingtools.com/api/v2/{storefront}/music/most-played/25/songs.json
"""
import re
import requests
from datetime import datetime
from database_config import TrendsCache
from dotenv import load_dotenv
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

load_dotenv()

logger = get_logger(__name__)


class MusicTrendsManager(BaseTrendsManager):
    """音楽トレンド取得（Apple Music RSS、認証・課金不要）"""

    # 地域コード → Apple Music storefront
    _STOREFRONT_MAP = {'JP': 'jp', 'US': 'us'}

    def __init__(self):
        super().__init__(service_name='music', max_requests=10, window_seconds=1)

    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す（地域別: music_trends_JP / music_trends_US）"""
        region = kwargs.get('region', 'JP')
        return f'music_trends_{region}'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.get_music_trends_from_cache(service, region)
        except Exception as e:
            logger.error(f"❌ Music: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.save_music_trends_to_cache(data, service, region)
        except Exception as e:
            logger.error(f"❌ Music キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            service = kwargs.get('service', 'spotify')
            region = kwargs.get('region', 'JP')
            return self.db.clear_music_trends_cache(service, region)
        except Exception as e:
            logger.error(f"❌ Music キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Music: cache_status更新エラー: {e}")
            return False

    def get_trends(self, service='spotify', region='JP', force_refresh=False):
        """音楽トレンドデータを取得（Apple Music RSS、キャッシュ優先）"""
        result = super().get_trends(
            limit=25,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
            sort_key='rank',
            sort_reverse=False,
            service=service,
            region=region
        )
        if result and isinstance(result, dict):
            result['service'] = service
            result['region_code'] = region
        return result

    def _fetch_trends(self, service='spotify', region='JP', *args, **kwargs):
        """Apple Music RSSからトレンドデータを取得"""
        try:
            logger.info(f"Apple Music RSS トレンド取得開始 (地域: {region})")

            trends = self._get_apple_music_rss(region, service)
            if not trends:
                logger.warning("楽曲が見つかりません")
                return {
                    'success': False,
                    'error': '楽曲が見つかりません',
                    'data': []
                }

            logger.info(f"✅ Apple Music RSS: {len(trends)}件のトレンドを取得 (region={region})")
            return {
                'success': True,
                'data': trends,
                'status': 'api_fetched',
                'source': 'Apple Music',
                'service': service,
                'region_code': region
            }

        except Exception as e:
            logger.error(f"Apple Music RSS エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Apple Music RSS エラー: {str(e)}',
                'data': []
            }

    @staticmethod
    def _extract_album_from_url(url: str) -> str | None:
        """
        Apple Music URL からアルバム名を抽出。
        https://music.apple.com/us/album/choosin-texas/1844932149?i=... の slug をタイトルに変換。
        """
        if not url:
            return None
        match = re.search(r'/album/([^/]+)/\d+', url)
        if not match:
            return None
        slug = match.group(1)
        # ハイフンをスペースに変換してタイトルケース化
        return slug.replace('-', ' ').title()

    def _get_apple_music_rss(self, region, service='spotify'):
        """
        Apple Music RSS から人気曲を取得。
        https://rss.applemarketingtools.com/api/v2/{storefront}/music/most-played/25/songs.json
        """
        storefront = self._STOREFRONT_MAP.get(region.upper(), region.lower())
        url = f"https://rss.applemarketingtools.com/api/v2/{storefront}/music/most-played/25/songs.json"

        try:
            logger.info(f"Apple Music RSS 取得: {url}")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Apple Music RSS 取得失敗: {e}")
            return None

        feed = data.get('feed', {}) or {}
        results = feed.get('results', [])
        if not results:
            logger.warning("Apple Music RSS: results が空です")
            return None

        trends = []
        for i, song in enumerate(results[:25], 1):
            try:
                track_id = str(song.get('id', f'applemusic_{storefront}_{i}'))
                title = song.get('name', '').strip()
                artist = (song.get('artistName') or 'Unknown').strip()
                url_link = song.get('url', '')
                album = self._extract_album_from_url(url_link) or 'Unknown'

                if not title:
                    continue

                # popularity: 順位の逆数（1位=100）
                popularity = max(0, 101 - i)
                play_count = (101 - i) * 10000  # 推定値（RSSに再生回数なし）

                trends.append({
                    'rank': i,
                    'title': title,
                    'artist': artist,
                    'play_count': play_count,
                    'album': album,
                    'spotify_url': url_link or f"https://music.apple.com/{storefront}/search?term={requests.utils.quote(title)}",
                    'popularity': popularity,
                    'days_since_published': 0,
                    'view_density': play_count,
                    'trend_score': play_count,
                    'service': service,
                    'region_code': region,
                    'created_at': datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),
                    'track_id': track_id
                })
            except Exception as e:
                logger.debug(f"楽曲パーススキップ (i={i}): {e}")
                continue

        return trends
