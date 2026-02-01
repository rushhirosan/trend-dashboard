import os
import re
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

class CNNTrendsManager(BaseTrendsManager):
    """CNNニューストレンドを取得・管理するクラス（NewsAPIを使用）"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='cnn', max_requests=10, window_seconds=60)
        
        # NewsAPIキーを取得（CNN RSSフィードが2024年8月で止まっているため、NewsAPIを使用）
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.news_api_base_url = "https://newsapi.org/v2"
        
        if not self.news_api_key:
            logger.warning("⚠️ NEWS_API_KEYが設定されていません。CNN記事は取得できません")
        else:
            logger.info("✅ CNN Trends Manager初期化: NewsAPIを使用して最新のCNN記事を取得します")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'cnn_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        cached_data = self.db.get_cnn_trends_from_cache()
        if cached_data:
            # 重複排除を適用
            cached_data = self._remove_duplicates(cached_data)
            # 古いデータをフィルタリング（過去7日間のデータのみ）
            today = datetime.now()
            cutoff_date = today - timedelta(days=7)
            filtered_cached_data = []
            for item in cached_data:
                published_date_str = item.get('published_date')
                if published_date_str:
                    try:
                        # ISO形式の文字列をdatetimeに変換
                        if isinstance(published_date_str, str):
                            published_date = datetime.fromisoformat(published_date_str.replace('Z', '+00:00'))
                            # タイムゾーン情報を削除して比較
                            published_date = published_date.replace(tzinfo=None)
                            # 過去7日間のデータのみを表示
                            if published_date >= cutoff_date:
                                filtered_cached_data.append(item)
                    except Exception as e:
                        logger.debug(f"⚠️ キャッシュデータの日付パースエラー: {published_date_str} - {e}")
                        continue
            return filtered_cached_data
        return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_cnn_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ CNN キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_cnn_trends_cache()
        except Exception as e:
            logger.error(f"❌ CNN キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ CNN: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """CNNニューストレンドを取得（キャッシュ優先、published_dateでソート）"""
        # キャッシュがない場合、過去7日間のデータがない場合はAPIを呼び出す
        cached_data = self._get_from_cache()
        if not cached_data or len(cached_data) == 0:
            if not force_refresh:
                logger.warning(f"⚠️ CNN: キャッシュに過去7日間の記事がありません。NewsAPIを呼び出します")
                # auto_fetch_on_cache_miss=TrueでAPIを呼び出す
                return super().get_trends(
                    limit=limit,
                    force_refresh=force_refresh,
                    auto_fetch_on_cache_miss=True,  # キャッシュがない場合はAPIを呼び出す
                    sort_key='published_date',  # 公開日でソート
                    sort_reverse=True  # 降順（新しい順）
                )
        
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持
        # sort_key='published_date'で公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='published_date',  # 公開日でソート
            sort_reverse=True  # 降順（新しい順）
        )

    def _remove_duplicates(self, items):
        """重複を排除するヘルパーメソッド"""
        def normalize_title(title):
            """タイトルを正規化（重複チェック用）"""
            if not title:
                return ''
            normalized = str(title).strip()
            normalized = re.sub(r'\s+', ' ', normalized)
            return normalized
        
        seen_urls = set()
        seen_titles = set()
        unique_items = []
        duplicate_count = 0
        
        for item in items:
            url = str(item.get('url', '')).strip()
            title = str(item.get('title', '')).strip()
            normalized_title = normalize_title(title)
            
            # URLまたは正規化されたタイトルが既に存在する場合はスキップ
            if url in seen_urls or normalized_title in seen_titles:
                duplicate_count += 1
                continue
            
            # 空のタイトルやURLはスキップ
            if not normalized_title or not url:
                duplicate_count += 1
                continue
            
            seen_urls.add(url)
            seen_titles.add(normalized_title)
            unique_items.append(item)
        
        if duplicate_count > 0:
            logger.info(f"🔄 CNN: キャッシュデータから{duplicate_count}件の重複を排除しました（残り: {len(unique_items)}件）")
        
        return unique_items
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """CNNニューストレンドデータを取得（NewsAPIのみ）"""
        if not self.news_api_key:
            logger.error("❌ NEWS_API_KEYが設定されていません。CNN記事を取得できません")
            return {
                'success': False,
                'error': 'NEWS_API_KEYが設定されていません',
                'data': []
            }
        return self._fetch_cnn_from_newsapi(limit)
    
    def _fetch_cnn_from_newsapi(self, limit=25):
        """NewsAPIからCNNの最新記事を取得"""
        try:
            logger.info(f"📰 NewsAPIからCNN記事を取得開始")
            
            # 最新の記事を取得するため、日付フィルタを追加
            # 過去7日間の記事を取得（最新データを確実に取得）
            today = datetime.now()
            from_date = today - timedelta(days=7)
            
            # NewsAPIのeverythingエンドポイントでCNNソースを指定
            # 英語版のCNN記事を優先的に取得
            url = f"{self.news_api_base_url}/everything"
            params = {
                'sources': 'cnn',
                'pageSize': limit,
                'sortBy': 'publishedAt',
                'language': 'en',  # 英語版を優先
                'from': from_date.strftime('%Y-%m-%dT%H:%M:%S'),  # 過去7日間の開始日
                'to': today.strftime('%Y-%m-%dT%H:%M:%S'),  # 今日まで
                'apiKey': self.news_api_key
            }
            
            logger.debug(f"NewsAPIリクエスト: {url} (sources=cnn)")
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ NewsAPI エラー: HTTP {response.status_code}")
                logger.error(f"エラーレスポンス: {response.text}")
                return {
                    'success': False,
                    'error': f'NewsAPI エラー: HTTP {response.status_code}',
                    'data': []
                }
            
            data = response.json()
            
            if data.get('status') != 'ok':
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"❌ NewsAPI レスポンスエラー: {error_msg}")
                return {
                    'success': False,
                    'error': f'NewsAPI エラー: {error_msg}',
                    'data': []
                }
            
            articles = data.get('articles', [])
            logger.info(f"✅ NewsAPIからCNN記事を{len(articles)}件取得")
            
            if len(articles) == 0:
                logger.warning("⚠️ NewsAPIでCNN記事が取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_articles',
                    'source': 'newsapi',
                    'message': 'CNN記事が見つかりませんでした'
                }
            
            # NewsAPIのレスポンスをCNN形式に変換
            formatted_data = []
            for i, article in enumerate(articles, 1):
                formatted_data.append({
                    'rank': i,
                    'title': article.get('title', 'No Title'),
                    'url': article.get('url', ''),
                    'published_date': article.get('publishedAt', ''),
                    'description': article.get('description', ''),
                    'source': 'CNN (via NewsAPI)'
                })
            
            # 公開日でソート（新しい順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            
            # 制限数まで取得
            formatted_data = formatted_data[:limit]
            
            logger.info(f"✅ CNN: NewsAPIから{len(formatted_data)}件の最新ニュース記事を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'newsapi',
                'total_count': len(formatted_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ NewsAPIタイムアウトエラー", exc_info=True)
            return {
                'success': False,
                'error': 'NewsAPIからの応答がタイムアウトしました',
                'data': []
            }
        except Exception as e:
            logger.error(f"❌ NewsAPI エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'NewsAPI エラー: {str(e)}',
                'data': []
            }
