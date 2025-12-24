import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

class NHKTrendsManager:
    """NHK RSSフィードを使用してニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # NHK RSSフィードURL
        self.rss_urls = {
            'main': 'https://www3.nhk.or.jp/rss/news/cat0.xml',  # 主要ニュース
            'domestic': 'https://www3.nhk.or.jp/rss/news/cat1.xml',  # 国内
            'international': 'https://www3.nhk.or.jp/rss/news/cat2.xml',  # 国際
            'economy': 'https://www3.nhk.or.jp/rss/news/cat3.xml',  # 経済
            'sports': 'https://www3.nhk.or.jp/rss/news/cat4.xml',  # スポーツ
            'science': 'https://www3.nhk.or.jp/rss/news/cat5.xml',  # 科学・文化
        }
        self.db = TrendsCache()
        # レート制限: NHK APIは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('nhk', max_requests=10, window_seconds=60)
        
        logger.info("NHK Trends Manager初期化:")
        logger.info(f"  RSS URL: {self.rss_urls['main']}")
    
    def get_trends(self, limit=25, force_refresh=False):
        """NHKニューストレンドを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            if force_refresh:
                logger.info(f"🔄 NHK force_refresh: キャッシュをクリアします")
                self.db.clear_nhk_trends_cache()
            
            try:
                cached_data = self.db.get_nhk_trends_from_cache()
            except Exception as e:
                logger.error(f"❌ NHK: キャッシュ取得エラー: {e}", exc_info=True)
                # エラー時は空のリストとして扱う（500エラーを防ぐ）
                cached_data = []
            
            if cached_data:
                # キャッシュから取得したデータにも重複排除を適用
                cached_data = self._remove_duplicates(cached_data)
                logger.info(f"✅ NHK: キャッシュから{len(cached_data)}件のデータを取得しました（重複排除後）")
                return {
                    'success': True,
                    'data': cached_data[:limit],  # 制限数まで取得
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                logger.warning("⚠️ NHK: キャッシュデータが見つかりません。外部RSSを呼び出します")
                return self._fetch_nhk_trends(limit)
        
        except Exception as e:
            logger.error(f"❌ NHK トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'NHKニュースの取得に失敗しました: {str(e)}', 'success': False}
    
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
    
    def _fetch_nhk_trends(self, limit=25):
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
            
            # 2. 国内（cat1）からトップ10件を取得
            try:
                url = self.rss_urls['domestic']
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    items = self._parse_rss_items(root)
                    all_items.extend(items[:10])  # トップ10件のみ
                    logger.info(f"✅ 国内: {len(items[:10])}件取得")
            except Exception as e:
                logger.warning(f"⚠️ 国内取得エラー: {e}")
            
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
            
            # 公開日でソート（新しい順）
            unique_items.sort(key=lambda x: x.get('published_date', ''), reverse=True)
            
            # 制限数まで取得
            formatted_data = unique_items[:limit]
            
            # ランクを追加
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            
            # キャッシュに保存
            self.db.save_nhk_trends_to_cache(formatted_data)
            logger.info(f"✅ NHK: {len(formatted_data)}件のニュース記事を取得しました")
            
            return {
                'success': True,
                'data': formatted_data,
                'status': 'api_fetched',
                'source': 'nhk_rss'
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

