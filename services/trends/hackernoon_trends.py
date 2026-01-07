import requests
import feedparser
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

class HackerNoonTrendsManager:
    """Hacker Noonトレンド管理クラス（RSSフィード使用）"""
    
    def __init__(self):
        """初期化"""
        # Hacker Noon RSSフィードURL
        self.rss_url = "https://hackernoon.com/feed"
        # フォールバック用のURL
        self.rss_alt_url = "https://hackernoon.com/tagged/technology/feed"
        self.db = TrendsCache()
        # レート制限: RSSフィードは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('hackernoon', max_requests=10, window_seconds=60)
        
        logger.info("Hacker Noon Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_url}")
    
    def get_trends(self, limit=25, force_refresh=False):
        """Hacker Noonトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 Hacker Noon force_refresh: キャッシュをクリアします")
                self.db.clear_hackernoon_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_hackernoon_trends_from_cache()
            
            if cached_data:
                # 公開日でソート（新しい順）
                cached_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                # キャッシュデータを使用する場合でも、cache_statusを更新
                if force_refresh:
                    try:
                        self.db.update_cache_status('hackernoon_trends', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ Hacker Noon: cache_status更新エラー（処理は継続）: {e}")
                
                logger.info(f"✅ Hacker Noon: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ Hacker Noon: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ Hacker Noon: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_hackernoon_trends(limit)
                
        except Exception as e:
            logger.error(f"❌ Hacker Noon トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Hacker Noonトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_hackernoon_trends(self, limit=25):
        """Hacker Noon RSSフィードからトレンドデータを取得"""
        try:
            logger.info(f"Hacker Noon RSS呼び出し開始")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # RSSフィードを取得（まずメインURLを試す）
            feed = feedparser.parse(self.rss_url)
            
            # メインURLが取得できない場合はフォールバックURLを試す
            if not feed.entries:
                logger.warning(f"⚠️ Hacker Noon メインRSSから取得失敗。フォールバックURLを試します")
                self.rate_limiter.wait_if_needed()
                feed = feedparser.parse(self.rss_alt_url)
            
            if not feed.entries:
                logger.warning("⚠️ Hacker Noon RSS: エントリーが見つかりませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'hackernoon_rss',
                    'message': '記事が見つかりませんでした'
                }
            
            logger.info(f"✅ Hacker Noon RSS: {len(feed.entries)}件のエントリーを取得")
            
            # データを整形
            formatted_data = []
            for i, entry in enumerate(feed.entries[:limit], 1):
                try:
                    # 公開日をパース
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except Exception as e:
                            logger.debug(f"日付パースエラー: {e}")
                            published_date = datetime.now()
                    elif hasattr(entry, 'published'):
                        try:
                            from email.utils import parsedate_to_datetime
                            published_date = parsedate_to_datetime(entry.published)
                        except Exception as e:
                            logger.debug(f"日付パースエラー: {e}")
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()
                    
                    # 説明文を取得
                    description = ''
                    if hasattr(entry, 'description'):
                        description = entry.description
                    elif hasattr(entry, 'summary'):
                        description = entry.summary
                    
                    formatted_item = {
                        'rank': i,
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description,
                        'author': entry.get('author', ''),
                        'source': 'Hacker Noon'
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ Hacker Noon エントリーパースエラー: {e}")
                    continue
            
            # 公開日でソート（新しい順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            
            # ランキングを再設定
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            
            # 制限数まで取得
            formatted_data = formatted_data[:limit]
            
            # キャッシュに保存
            if formatted_data:
                self.db.save_hackernoon_trends_to_cache(formatted_data)
                self.db.update_cache_status('hackernoon_trends', len(formatted_data))
            
            logger.info(f"✅ Hacker Noon: {len(formatted_data)}件の記事を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'hackernoon_rss',
                'total_count': len(formatted_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ Hacker Noon RSS タイムアウトエラー", exc_info=True)
            return {
                'error': 'Hacker Noon RSS タイムアウト',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ Hacker Noon RSS エラー: {e}", exc_info=True)
            return {
                'error': f'Hacker Noon RSS取得エラー: {str(e)}',
                'success': False
            }

