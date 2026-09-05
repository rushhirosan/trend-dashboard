import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)

# ニュース速報の張り付き防止（URL 日付 / published_date がこれより古い記事は除外）
_NHK_MAX_AGE_DAYS = 3
# 旧 NEWS WEB: /html/YYYYMMDD/  /  NHK ONE: nd-YYYYMMDD...
_NHK_URL_DATE_RE = re.compile(r"(?:/html/|nd-)(\d{8})")

# NHK ONE RSS（2025-10 の NEWS WEB 集約後。www3 は更新停止で 200 のまま古い記事を返す）
# https://www.nhk.or.jp/toppage/rss/index.html
NHK_RSS_URLS = {
    "main": "https://news.web.nhk/n-data/conf/na/rss/cat0.xml",  # 主要ニュース
    "domestic": "https://news.web.nhk/n-data/conf/na/rss/cat1.xml",  # 社会
    "international": "https://news.web.nhk/n-data/conf/na/rss/cat6.xml",  # 国際
    "economy": "https://news.web.nhk/n-data/conf/na/rss/cat5.xml",  # 経済
    "sports": "https://news.web.nhk/n-data/conf/na/rss/cat7.xml",  # スポーツ
    "science": "https://news.web.nhk/n-data/conf/na/rss/cat3.xml",  # 科学・医療
}


class NHKTrendsManager(BaseTrendsManager):
    """NHK RSSフィードを使用してニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='nhk', max_requests=10, window_seconds=60)
        
        self.rss_urls = dict(NHK_RSS_URLS)
        
        logger.info("NHK Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_urls['main']}")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'nhk_trends'

    def _article_datetime(self, item: dict):
        """published_date または URL 内の日付（/html/YYYYMMDD/ または nd-YYYYMMDD）から記事日時を推定。"""
        published_date_str = item.get("published_date")
        if published_date_str:
            try:
                if isinstance(published_date_str, datetime):
                    return published_date_str.replace(tzinfo=None)
                published_date = datetime.fromisoformat(
                    str(published_date_str).replace("Z", "+00:00")
                )
                return published_date.replace(tzinfo=None)
            except Exception:
                pass
        url = str(item.get("url") or "")
        m = _NHK_URL_DATE_RE.search(url)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y%m%d")
            except ValueError:
                return None
        return None

    def _filter_fresh(self, items: list, *, max_age_days: int = _NHK_MAX_AGE_DAYS) -> list:
        """公開から max_age_days 以内の記事だけ残す（日付不明は残す）。"""
        if not items:
            return []
        cutoff = datetime.now() - timedelta(days=max_age_days)
        fresh = []
        dropped = 0
        for item in items:
            article_dt = self._article_datetime(item)
            if article_dt is not None and article_dt < cutoff:
                dropped += 1
                continue
            fresh.append(item)
        if dropped:
            logger.info(
                f"🔄 NHK: {dropped}件の古い記事を除外しました"
                f"（{max_age_days}日超・残り: {len(fresh)}件）"
            )
        return fresh

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得（古い記事は除外。空なら RSS 再取得を促す）。"""
        try:
            cached = self.db.get_nhk_trends_from_cache() or []
            return self._filter_fresh(cached)
        except Exception as e:
            logger.error(f"❌ NHK: キャッシュ取得エラー: {e}", exc_info=True)
            return []

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_nhk_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ NHK キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_nhk_trends_cache()
        except Exception as e:
            logger.error(f"❌ NHK キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ NHK: cache_status更新エラー: {e}")
            return False

    def get_trends(self, limit=25, force_refresh=False):
        """NHKニューストレンドを取得（キャッシュ優先、published_dateでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=True: キャッシュ空時は RSS を取得（定期失敗後の画面でも復旧しやすい）
        # sort_key='published_date'で公開日でソート
        return super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,
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
            logger.info(f"🔄 NHK: キャッシュデータから{duplicate_count}件の重複を排除しました（残り: {len(unique_items)}件）")
        
        return unique_items
    
    def _parse_rss_items(self, root):
        """RSS XMLからアイテムをパース"""
        items = []
        for item in root.findall('.//item'):
            try:
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')
                
                if title is not None and link is not None:
                    # 公開日をパース
                    published_date = None
                    if pub_date is not None and pub_date.text:
                        try:
                            # RFC 822形式の日付をパース
                            from email.utils import parsedate_to_datetime
                            published_date = parsedate_to_datetime(pub_date.text)
                        except Exception as e:
                            logger.debug(f"日付パースエラー: {e}")
                            published_date = datetime.now()
                    
                    items.append({
                        'title': title.text if title is not None else '',
                        'url': link.text if link is not None else '',
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description.text if description is not None else ''
                    })
            except Exception as e:
                logger.warning(f"NHK RSS アイテムパースエラー: {e}")
                continue
        
        return items
    
    def _fetch_trends(self, limit=25, *args, **kwargs):
        """NHK RSSフィードからトレンドデータを取得"""
        try:
            logger.info(f"NHK RSS呼び出し開始")
            
            all_items = []
            
            # 1. 主要ニュース（cat0）から取得
            try:
                url = self.rss_urls['main']
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    items = self._parse_rss_items(root)
                    all_items.extend(items)
                    logger.info(f"✅ 主要ニュース: {len(items)}件取得")
            except Exception as e:
                logger.warning(f"⚠️ 主要ニュース取得エラー: {e}")
            
            # 2. 社会（cat1）からトップ10件を取得
            try:
                url = self.rss_urls['domestic']
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    items = self._parse_rss_items(root)
                    all_items.extend(items[:10])  # トップ10件のみ
                    logger.info(f"✅ 社会: {len(items[:10])}件取得")
            except Exception as e:
                logger.warning(f"⚠️ 社会取得エラー: {e}")
            
            # 3. 国際（cat2）からトップ10件を取得
            try:
                url = self.rss_urls['international']
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    items = self._parse_rss_items(root)
                    all_items.extend(items[:10])  # トップ10件のみ
                    logger.info(f"✅ 国際: {len(items[:10])}件取得")
            except Exception as e:
                logger.warning(f"⚠️ 国際取得エラー: {e}")
            
            if len(all_items) == 0:
                logger.warning("NHK RSSで記事が取得できませんでした")
                return {
                    'error': 'NHK RSSで記事が取得できませんでした',
                    'success': False
                }
            
            # 重複排除（共通メソッドを使用）
            unique_items = self._remove_duplicates(all_items)
            unique_items = self._filter_fresh(unique_items)

            if len(unique_items) == 0:
                logger.warning("NHK RSS: 鮮度フィルタ後に記事が残りませんでした")
                return {
                    'error': 'NHK RSSで新しい記事が取得できませんでした',
                    'success': False
                }

            # 公開日でソート（新しい順）
            unique_items.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            
            # 制限数まで取得
            formatted_data = unique_items[:limit]
            
            # ランクを追加
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            
            logger.info(f"✅ NHK: {len(formatted_data)}件のニュース記事を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'nhk_rss',
                'total_count': len(formatted_data)
            }
        
        except requests.exceptions.Timeout:
            logger.error("❌ NHK RSSタイムアウトエラー", exc_info=True)
            return {'error': 'NHK RSSからの応答がタイムアウトしました', 'success': False}
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ NHK RSSリクエストエラー: {e}", exc_info=True)
            return {'error': f'NHK RSSリクエスト中にエラーが発生しました: {str(e)}', 'success': False}
        except ET.ParseError as e:
            logger.error(f"❌ NHK RSS XMLパースエラー: {e}", exc_info=True)
            return {'error': f'NHK RSS XMLのパースに失敗しました: {str(e)}', 'success': False}
        except Exception as e:
            logger.error(f"❌ NHKニュース取得エラー: {e}", exc_info=True)
            return {'error': f'NHKニュースの取得に失敗しました: {str(e)}', 'success': False}
