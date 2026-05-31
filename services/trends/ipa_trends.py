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
            # 例: /2025/alert20260119.html → 2026年1月19日（年が異なる場合も対応）
            pattern1 = r'/(\d{4})/alert(\d{8})\.html'
            match1 = re.search(pattern1, url)
            if match1:
                year_path = int(match1.group(1))
                date_str = match1.group(2)  # YYYYMMDD形式
                if len(date_str) == 8:
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    # パスの年と日付の年が異なる場合でも、日付の年を優先
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
            
            # パターン5: /YYYY/YYYYMMDD.html（サフィックスなし）
            # 例: /2025/20251208.html → 2025年12月8日
            pattern5 = r'/(\d{4})/(\d{8})\.html'
            match5 = re.search(pattern5, url)
            if match5:
                year = int(match5.group(1))
                date_str = match5.group(2)  # YYYYMMDD形式
                if len(date_str) == 8:
                    year_from_date = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    if year_from_date == year:
                        try:
                            return datetime(year, month, day)
                        except ValueError as e:
                            logger.debug(f"IPA URL日付パースエラー: {url}, {e}")
            
            # パターン6: alertYYYYMMDD.html（年がパスにない場合のフォールバック）
            pattern7 = r'alert(\d{8})\.html'
            match7 = re.search(pattern7, url)
            if match7:
                date_str = match7.group(1)
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
    
    def _fetch_original_published_date_from_html(self, url):
        """
        HTMLページから実際の公開日を取得（URLパターンから抽出できない場合のフォールバック）
        """
        if not url:
            return None
        
        try:
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # テキストから日付を抽出
                text = soup.get_text()
                
                # パターン1: 公開日：2024年10月15日
                date_pattern1 = r'公開日[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日'
                match1 = re.search(date_pattern1, text)
                if match1:
                    year = int(match1.group(1))
                    month = int(match1.group(2))
                    day = int(match1.group(3))
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA HTML日付パースエラー: {url}, {e}")
                
                # パターン2: 公開日：2024/10/15
                date_pattern2 = r'公開日[：:]\s*(\d{4})/(\d{1,2})/(\d{1,2})'
                match2 = re.search(date_pattern2, text)
                if match2:
                    year = int(match2.group(1))
                    month = int(match2.group(2))
                    day = int(match2.group(3))
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA HTML日付パースエラー: {url}, {e}")
                        
        except Exception as e:
            logger.debug(f"IPA HTML日付取得エラー: {url}, {e}")
        
        return None
    
    def _fetch_last_updated_date_from_html(self, url):
        """
        HTMLページから最終更新日を取得
        """
        if not url:
            return None
        
        try:
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # テキストから日付を抽出
                text = soup.get_text()
                
                # パターン1: 最終更新日：2025年10月16日
                date_pattern1 = r'最終更新日[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日'
                match1 = re.search(date_pattern1, text)
                if match1:
                    year = int(match1.group(1))
                    month = int(match1.group(2))
                    day = int(match1.group(3))
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA HTML最終更新日パースエラー: {url}, {e}")
                
                # パターン2: 最終更新日：2025/10/16
                date_pattern2 = r'最終更新日[：:]\s*(\d{4})/(\d{1,2})/(\d{1,2})'
                match2 = re.search(date_pattern2, text)
                if match2:
                    year = int(match2.group(1))
                    month = int(match2.group(2))
                    day = int(match2.group(3))
                    try:
                        return datetime(year, month, day)
                    except ValueError as e:
                        logger.debug(f"IPA HTML最終更新日パースエラー: {url}, {e}")
                        
        except Exception as e:
            logger.debug(f"IPA HTML最終更新日取得エラー: {url}, {e}")
        
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
    
    def _normalize_title(self, title):
        """
        タイトルを正規化して比較用のキーを生成
        「更新：」や「更新:」を除去して、同じトピックかどうかを判定
        """
        if not title:
            return ''
        # 「更新：」「更新:」を除去
        normalized = re.sub(r'^更新[：:]\s*', '', title)
        return normalized.strip()
    
    def _remove_duplicates(self, data):
        """
        重複する記事を除去
        同じトピック（タイトルから「更新：」を除去したもの）が複数ある場合、
        以下の優先順位で1つだけ残す：
        1. 最終更新日がある記事（更新版）を優先
        2. 最終更新日がない場合は、公開日が新しいものを優先
        3. それでも同じ場合は、タイトルに「更新：」が含まれているものを優先
        """
        if not data:
            return data
        
        # タイトルを正規化してグループ化
        title_groups = {}
        for item in data:
            normalized_title = self._normalize_title(item.get('title', ''))
            if normalized_title not in title_groups:
                title_groups[normalized_title] = []
            title_groups[normalized_title].append(item)
        
        # 各グループから最適な記事を1つだけ選択
        result = []
        for normalized_title, items in title_groups.items():
            if len(items) == 1:
                # 重複がない場合はそのまま追加
                result.append(items[0])
            else:
                # 重複がある場合は優先順位で選択
                # 1. 最終更新日がある記事を優先
                items_with_update = [item for item in items if item.get('last_updated_date')]
                items_without_update = [item for item in items if not item.get('last_updated_date')]
                
                if items_with_update:
                    # 最終更新日がある記事の中から、最新のものを選択
                    selected = max(items_with_update, key=lambda x: (
                        x.get('last_updated_date') or '',
                        x.get('original_published_date') or x.get('published_date') or '',
                        self._is_updated_alert(x.get('title', ''))
                    ))
                elif items_without_update:
                    # 最終更新日がない記事の中から、最新のものを選択
                    selected = max(items_without_update, key=lambda x: (
                        x.get('original_published_date') or x.get('published_date') or '',
                        self._is_updated_alert(x.get('title', ''))
                    ))
                else:
                    # フォールバック（通常は発生しない）
                    selected = items[0]
                
                result.append(selected)
                logger.debug(f"重複除去: '{normalized_title}' から {len(items)}件中1件を選択")
        
        return result

    def _publication_date(self, item):
        """初出記事のソート用公開日"""
        return item.get('original_published_date') or item.get('published_date') or ''

    def _is_update_item(self, item):
        """更新記事かどうか（キャッシュには is_updated が無い場合はタイトルで判定）"""
        if item.get('is_updated') is not None:
            return bool(item.get('is_updated'))
        return self._is_updated_alert(item.get('title', ''))

    def _sort_ipa_items(self, data):
        """新規注意喚起を先に、更新記事を後に、各グループ内は日付の新しい順"""
        if not data:
            return data

        new_items = [x for x in data if not self._is_update_item(x)]
        update_items = [x for x in data if self._is_update_item(x)]

        new_items.sort(key=self._publication_date, reverse=True)
        update_items.sort(
            key=lambda x: x.get('last_updated_date') or self._publication_date(x),
            reverse=True,
        )
        return new_items + update_items
    
    def _get_cache_key(self, *args, **kwargs):
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
        """IPA注意喚起トレンドを取得（キャッシュ優先、新規を更新より先にソート）"""
        # ベースクラスのget_trendsを使用（sort_keyはNoneにして、後でカスタムソートを適用）
        result = super().get_trends(
            limit=limit * 2,  # ソートのために少し多めに取得
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
            sort_key=None,  # カスタムソートを適用するためNone
            sort_reverse=True  # 降順（新しい順）
        )
        
        if result.get('success') and result.get('data'):
            data = result['data']
            # 重複除去を実行（ソートの前に行う）
            original_count = len(data)
            data = self._remove_duplicates(data)
            removed_count = original_count - len(data)
            if removed_count > 0:
                logger.info(f"✅ IPA: キャッシュから取得したデータから {removed_count}件の重複記事を除去しました（{original_count}件 → {len(data)}件）")
            data = self._sort_ipa_items(data)
            # 制限数まで取得
            data = data[:limit]
            # rankを再設定（1から始まる）
            for i, item in enumerate(data, 1):
                item['rank'] = i
            result['data'] = data
        
        return result
    
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
                    
                    # URLパターンから抽出できない場合、HTMLページから取得を試す
                    # パフォーマンスを考慮して、限定的に使用（日付が含まれていないパターンのみ）
                    if not original_published_date:
                        # ファイル名に日付パターン（8桁の数字）が含まれていない場合のみ
                        filename = entry_url.split('/')[-1] if '/' in entry_url else entry_url
                        if not re.search(r'\d{8}', filename):
                            # 日付が含まれていないパターン（例：win10_eos.html）
                            original_published_date = self._fetch_original_published_date_from_html(entry_url)
                    
                    # タイトルを取得
                    title = entry.get('title', 'No Title')
                    
                    # 更新情報かどうかを判定
                    is_updated = self._is_updated_alert(title)
                    
                    # 最終更新日を取得（更新された記事のみHTMLから取得）
                    # パフォーマンスを考慮して、更新された記事のみHTMLから取得
                    last_updated_date = None
                    if is_updated:
                        # 更新された記事はHTMLから最終更新日を取得
                        last_updated_date = self._fetch_last_updated_date_from_html(entry_url)
                    
                    # 実際の公開日を優先（取得できた場合）
                    published_date = original_published_date if original_published_date else rss_published_date
                    
                    # 説明文を取得
                    description = ''
                    if hasattr(entry, 'description'):
                        description = entry.description
                    elif hasattr(entry, 'summary'):
                        description = entry.summary
                    
                    formatted_item = {
                        'title': title,
                        'url': entry_url,
                        'published_date': published_date.isoformat() if published_date else None,
                        'original_published_date': original_published_date.isoformat() if original_published_date else None,
                        'rss_published_date': rss_published_date.isoformat() if rss_published_date else None,
                        'last_updated_date': last_updated_date.isoformat() if last_updated_date else None,
                        'is_updated': is_updated,  # 更新情報かどうか
                        'description': description,
                        'author': entry.get('author', ''),
                        'source': 'IPA',
                    }
                    formatted_data.append(formatted_item)
                except Exception as e:
                    logger.warning(f"⚠️ IPA エントリーパースエラー: {e}")
                    continue
            
            # 重複除去を実行（ソートの前に行う）
            original_count = len(formatted_data)
            formatted_data = self._remove_duplicates(formatted_data)
            removed_count = original_count - len(formatted_data)
            if removed_count > 0:
                logger.info(f"✅ IPA: {removed_count}件の重複記事を除去しました（{original_count}件 → {len(formatted_data)}件）")
            
            formatted_data = self._sort_ipa_items(formatted_data)
            
            # 制限数まで取得
            formatted_data = formatted_data[:limit]
            
            # rankを設定（1から始まる）
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            
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
