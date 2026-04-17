import requests
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

class JPCERTTrendsManager(BaseTrendsManager):
    """JPCERT/CCトレンド管理クラス（RSSフィード使用）"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='jpcert', max_requests=10, window_seconds=60)
        
        # JPCERT/CC RSSフィードURL
        self.rss_url = "https://www.jpcert.or.jp/rss/jpcert.rdf"
        # jpcert.xml は404のため、公式サイト掲載の広域フィードへフォールバック
        self.rss_fallback_url = "https://www.jpcert.or.jp/rss/jpcert-all.rdf"

        self._http = requests.Session()
        self._http.headers.update({
            'User-Agent': 'TrendDashboard/1.0 (trend detection; link-out only)',
            'Accept': 'application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        })
        
        logger.info("JPCERT/CC Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_url}")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'jpcert_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_jpcert_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_jpcert_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ JPCERT/CC キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_jpcert_trends_cache()
        except Exception as e:
            logger.error(f"❌ JPCERT/CC キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ JPCERT/CC: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """JPCERT/CCトレンドを取得（キャッシュ優先、published_dateでソート）"""
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

    def _parse_feed_from_url(self, url, label):
        """HTTPで本文を取得してからパース（feedparser の URL 直読みは環境によって 0 件になる）"""
        self.rate_limiter.wait_if_needed()
        try:
            resp = self._http.get(url, timeout=20)
        except requests.exceptions.Timeout:
            logger.error(f"❌ JPCERT/CC RSS タイムアウト ({label})", exc_info=True)
            raise
        if resp.status_code != 200:
            logger.warning(f"⚠️ JPCERT/CC RSS HTTP {resp.status_code} ({label})")
            return feedparser.parse(b'')
        parsed = feedparser.parse(resp.content)
        if getattr(parsed, 'bozo', False) and getattr(parsed, 'bozo_exception', None):
            logger.warning(
                f"⚠️ JPCERT/CC RSS パース警告 ({label}): {parsed.bozo_exception}"
            )
        return parsed

    def _published_datetime(self, entry):
        """RSS 1.0 の dc:date は updated に入ることが多いため両方を見る"""
        time_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if time_struct:
            try:
                return datetime(*time_struct[:6])
            except Exception as e:
                logger.debug(f"日付パースエラー(time_struct): {e}")
        for key in ('published', 'updated'):
            val = entry.get(key)
            if not val:
                continue
            if isinstance(val, datetime):
                return val
            s = str(val).strip()
            try:
                return parsedate_to_datetime(s)
            except Exception:
                pass
            try:
                if 'T' in s or s[:4].isdigit() and s[4:5] == '-':
                    return datetime.fromisoformat(s.replace('Z', '+00:00'))
            except Exception as e:
                logger.debug(f"日付パースエラー(fromisoformat {key}): {e}")
        return datetime.now()
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """JPCERT/CC RSSフィードからトレンドデータを取得"""
        try:
            logger.info(f"JPCERT/CC RSS呼び出し開始")
            
            feed = self._parse_feed_from_url(self.rss_url, 'primary')

            if not feed.entries:
                logger.warning("⚠️ JPCERT/CC メインRSSからエントリーなし。フォールバックを試します")
                feed = self._parse_feed_from_url(self.rss_fallback_url, 'fallback')
            
            if not feed.entries:
                logger.warning("⚠️ JPCERT/CC RSS: エントリーが見つかりませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'jpcert_rss',
                    'message': '記事が見つかりませんでした'
                }
            
            logger.info(f"✅ JPCERT/CC RSS: {len(feed.entries)}件のエントリーを取得")
            
            # データを整形
            formatted_data = []
            for entry in feed.entries[:limit]:
                try:
                    published_date = self._published_datetime(entry)
                    
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
                        'source': 'JPCERT/CC'
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ JPCERT/CC エントリーパースエラー: {e}")
                    continue
            
            # 公開日でソート（新しい順）
            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            
            # 制限数まで取得
            formatted_data = formatted_data[:limit]
            
            logger.info(f"✅ JPCERT/CC: {len(formatted_data)}件の注意喚起情報を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'jpcert_rss',
                'total_count': len(formatted_data)
            }
            
        except requests.exceptions.Timeout:
            logger.error("❌ JPCERT/CC RSS タイムアウトエラー", exc_info=True)
            return {
                'error': 'JPCERT/CC RSS タイムアウト',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ JPCERT/CC RSS エラー: {e}", exc_info=True)
            return {
                'error': f'JPCERT/CC RSS取得エラー: {str(e)}',
                'success': False
            }
