import requests
import feedparser
import re
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
    
    def _extract_published_date_from_url(self, url):
        """
        IPAのURLパターンから実際の公開日を抽出
        対応パターン:
        - /YYYY/alertYYYYMMDD.html → /2025/alert20250827.html
        - /YYYY/YYYYMMDD-suffix.html → /2025/20250827-jvn.html
        - /YYYY/MMDD-suffix.html → /2025/0910-ms.html（年はパスから）
        - alertYYYYMMDD_suffix.html → alert20251031_router.html
        """
        if not url:
            return None
        
        try:
            # パターン1: /YYYY/alertYYYYMMDD.html
            # 例: /2025/alert20250827.html → 2025年8月27日
            pattern1 = r'/(\d{4})/alert(\d{8})\.html'
            match1 = re.search(pattern1, url)
            if match1:
                year = int(match1.group(1))
                date_str = match1.group(2)  # YYYYMMDD形式
                if len(date_str) == 8:
                    year_from_date = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if year_from_date == year:
                        try:
                            return datetime(year, month, day)
                        except ValueError as e:
                            logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
            
            # パターン2: /YYYY/YYYYMMDD-suffix.html
            # 例: /2025/20250827-jvn.html → 2025年8月27日
            pattern2 = r'/(\d{4})/(\d{8})-[\w-]+\.html'
            match2 = re.search(pattern2, url)
            if match2:
                year = int(match2.group(1))
                date_str = match2.group(2)  # YYYYMMDD形式
                if len(date_str) == 8:
                    year_from_date = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if year_from_date == year:
                        try:
                            return datetime(year, month, day)
                        except ValueError as e:
                            logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
            
            # パターン3: /YYYY/MMDD-suffix.html
            # 例: /2025/0910-ms.html → 2025年9月10日（年はパスから）
            pattern3 = r'/(\d{4})/(\d{4})-[\w-]+\.html'
            match3 = re.search(pattern3, url)
            if match3:
                year = int(match3.group(1))
                date_str = match3.group(2)  # MMDD形式
                if len(date_str) == 4:
                    month = int(date_str[:2])
                    day = int(date_str[2:4])
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
            
            # パターン4: alertYYYYMMDD_suffix.html
            # 例: alert20251031_router.html → 2025年10月31日
            pattern4 = r'alert(\d{8})_[\w-]+\.html'
            match4 = re.search(pattern4, url)
            if match4:
                date_str = match4.group(1)  # YYYYMMDD形式
                if len(date_str) == 8:
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
            
            # パターン5: alertYYYYMMDD.html（年がパスにない場合のフォールバック）
            pattern5 = r'alert(\d{8})\.html'
            match5 = re.search(pattern5, url)
            if match5:
                date_str = match5.group(1)
                if len(date_str) == 8:
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
                    
        except Exception as e:
            logger.debug(f"IPA URL日付抽出エラー: {url}, {e}")
        
        return None
    
    def _is_updated_alert(self, title):
        """
        タイトルに「更新：」が含まれているかチェック
        実際に内容が更新された情報かどうかを判定
        """
        if not title:
            return False
        # 「更新：」「更新:」のいずれかが含まれているか
        return '更新：' in title or '更新:' in title
    
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
        """IPA注意喚起トレンドを取得（キャッシュ優先、実際の公開日でソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        # sort_key='published_date'で実際の公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            sort_key='published_date',  # 実際の公開日でソート
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
                    # RSSフィードの公開日（RSS配信日）を取得
                    rss_published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            rss_published_date = datetime(*entry.published_parsed[:6])
                        except Exception as e:
                            logger.debug(f"日付パースエラー: {e}")
                            rss_published_date = datetime.now()
                    elif hasattr(entry, 'published'):
                        try:
                            from email.utils import parsedate_to_datetime
                            rss_published_date = parsedate_to_datetime(entry.published)
                        except Exception as e:
                            logger.debug(f"日付パースエラー: {e}")
                            rss_published_date = datetime.now()
                    else:
                        rss_published_date = datetime.now()
                    
                    # URLから実際の公開日を抽出
                    entry_url = entry.get('link', '')
                    original_published_date = self._extract_published_date_from_url(entry_url)
                    
                    # タイトルを取得
                    title = entry.get('title', 'No Title')
                    
                    # 実際の公開日を優先（取得できた場合）
                    # タイトルに「更新：」がある場合は、更新情報として扱うが、
                    # ソートは元の公開日で行う（更新日ではない）
                    published_date = original_published_date if original_published_date else rss_published_date
                    
                    # 説明文を取得
                    description = ''
                    if hasattr(entry, 'description'):
                        description = entry.description
                    elif hasattr(entry, 'summary'):
                        description = entry.summary
                    
                    # 更新情報かどうかを判定
                    is_updated = self._is_updated_alert(title)
                    
                    formatted_item = {
                        'title': title,
                        'url': entry_url,
                        'published_date': published_date.isoformat() if published_date else None,
                        'original_published_date': original_published_date.isoformat() if original_published_date else None,
                        'rss_published_date': rss_published_date.isoformat() if rss_published_date else None,
                        'is_updated': is_updated,  # 更新情報かどうか
                        'description': description,
                        'author': entry.get('author', ''),
                        'source': 'IPA'
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ IPA エントリーパースエラー: {e}")
                    continue
            
            # 実際の公開日（original_published_date）でソート、なければpublished_dateでソート
            # 更新情報（is_updated=True）の場合は、元の公開日でソートするが、
            # 同じ公開日の場合は更新情報を少し優先（ただし、これは元の公開日が同じ場合のみ）
            formatted_data.sort(
                key=lambda x: (
                    x.get('original_published_date') or x.get('published_date') or '',
                    x.get('is_updated', False)  # 更新情報は同じ日付内で少し優先
                ),
                reverse=True
            )
            
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
