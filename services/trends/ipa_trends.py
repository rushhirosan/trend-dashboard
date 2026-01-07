import requests
import feedparser
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

class IPATrendsManager:
    """IPA注意喚起トレンド管理クラス（RSSフィード使用）"""
    
    def __init__(self):
        """初期化"""
        # IPA注意喚起RSSフィードURL
        self.rss_url = "https://www.ipa.go.jp/security/rss/alert.rdf"
        # フォールバック用のXML URL
        self.rss_xml_url = "https://www.ipa.go.jp/security/rss/alert.xml"
        self.db = TrendsCache()
        # レート制限: RSSフィードは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('ipa', max_requests=10, window_seconds=60)
        
        logger.info("IPA Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_url}")
    
    def get_trends(self, limit=25, force_refresh=False):
        """IPA注意喚起トレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 IPA force_refresh: キャッシュをクリアします")
                self.db.clear_ipa_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_ipa_trends_from_cache()
            
            if cached_data:
                # 公開日でソート（新しい順）
                cached_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                # キャッシュデータを使用する場合でも、cache_statusを更新
                if force_refresh:
                    try:
                        self.db.update_cache_status('ipa_trends', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ IPA: cache_status更新エラー（処理は継続）: {e}")
                
                logger.info(f"✅ IPA: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ IPA: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ IPA: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_ipa_trends(limit)
                
        except Exception as e:
            logger.error(f"❌ IPA トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'IPA注意喚起トレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_ipa_trends(self, limit=25):
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
                        'source': 'IPA'
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ IPA エントリーパースエラー: {e}")
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
                self.db.save_ipa_trends_to_cache(formatted_data)
                self.db.update_cache_status('ipa_trends', len(formatted_data))
            
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

