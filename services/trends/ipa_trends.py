import requests
import feedparser
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

class IPATrendsManager(BaseTrendsManager):
    """IPA注意喚起トレンド管理クラス（RSSフィード使用）"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='ipa', max_requests=10, window_seconds=60)
        
        # IPA注意喚起RSSフィードURL
        self.rss_url = "https://www.ipa.go.jp/security/rss/alert.rdf"
        # フォールバック用のXML URL
        self.rss_xml_url = "https://www.ipa.go.jp/security/rss/alert.xml"
        
        logger.info("IPA Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_url}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'ipa_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_ipa_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_ipa_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ IPA キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_ipa_trends_cache()
        except Exception as e:
            logger.error(f"❌ IPA キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ IPA: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """IPA注意喚起トレンドを取得（キャッシュ優先、published_dateでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='published_date'で公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='published_date',  # 公開日でソート
            sort_reverse=True  # 降順（新しい順）
        )
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """IPA注意喚起RSSフィードからトレンドデータを取得"""
        try:
            logger.info(f"IPA RSS呼び出し開始")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # RSSフィードを取得（まずRDFを試す）
            feed = feedparser.parse(self.rss_url)
            
            # RDFが取得できない場合はXMLを試す
            if not feed.entries:
                logger.warning(f"⚠️ IPA RDFから取得失敗。XMLを試します")
                self.rate_limiter.wait_if_needed()
                feed = feedparser.parse(self.rss_xml_url)
            
            if not feed.entries:
                logger.warning("⚠️ IPA RSS: エントリーが見つかりませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'ipa_rss',
                    'message': '記事が見つかりませんでした'
                }
            
            logger.info(f"✅ IPA RSS: {len(feed.entries)}件のエントリーを取得")
            
            # データを整形
            formatted_data = []
            for entry in feed.entries[:limit]:
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
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description,
                        'author': entry.get('author', ''),
                        'source': 'IPA'
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ IPA エントリーパースエラー: {e}")
                    continue
            
            # 公開日でソート（新しい順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            
            # 制限数まで取得
            formatted_data = formatted_data[:limit]
            
            logger.info(f"✅ IPA: {len(formatted_data)}件の注意喚起情報を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'ipa_rss',
                'total_count': len(formatted_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ IPA RSS タイムアウトエラー", exc_info=True)
            return {
                'error': 'IPA RSS タイムアウト',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ IPA RSS エラー: {e}", exc_info=True)
            return {
                'error': f'IPA RSS取得エラー: {str(e)}',
                'success': False
            }
