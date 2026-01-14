import os
import requests
import json
import feedparser
import urllib.parse
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class HatenaTrendsManager(BaseTrendsManager):
    """はてなブックマークトレンド管理クラス（公式RSS + API使用）"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='hatena', max_requests=10, window_seconds=60)
        
        self.base_url = "https://b.hatena.ne.jp"
        self.count_api_url = "https://bookmark.hatenaapis.com/count/entry"
        self.entry_api_url = "https://b.hatena.ne.jp/entry/json"
        
        logger.info(f"はてなブックマーク Trends Manager初期化:")
        logger.info(f"  ホットエントリーRSS: {self.base_url}/hotentry.rss")
        logger.info(f"  Count API: {self.count_api_url}")
        logger.info(f"  Entry API: {self.entry_api_url}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'hatena_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            category = kwargs.get('category', 'all')
            cached_data = self.db.get_hatena_trends_from_cache(category)
            
            if cached_data:
                # categoryでフィルタリング（念のため）
                category_data = [item for item in cached_data if item.get('category') == category]
                logger.debug(f"🔍 はてなブックマーク: キャッシュから{len(category_data)}件のデータを取得 (category: {category})")
                return category_data
            else:
                logger.debug(f"🔍 はてなブックマーク: キャッシュにデータがありません (category: {category})")
                return []
        except Exception as e:
            logger.error(f"❌ Hatena: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            category = kwargs.get('category', 'all')
            return self.db.save_hatena_trends_to_cache(data, category)
        except Exception as e:
            logger.error(f"❌ Hatena キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            category = kwargs.get('category', 'all')
            return self.db.clear_hatena_trends_cache(category)
        except Exception as e:
            logger.error(f"❌ Hatena キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Hatena: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, category='all', limit=25, *args, **kwargs):
        """外部APIからはてなブックマークデータを取得"""
        result = self.get_new_entries(category, limit)
        if result and not result.get('error'):
            trends_data = result.get('data', [])
            # カテゴリ情報を追加
            for item in trends_data:
                item['category'] = category
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'category': category,
                'source': 'Hatena API'
            }
        else:
            return {
                'success': False,
                'error': result.get('error', 'Unknown error') if result else 'API call failed',
                'data': [],
                'status': 'api_error',
                'category': category
            }

    def get_trends(self, category='all', limit=25, force_refresh=False, fetch_all_categories=False):
        """はてなブックマークトレンドを取得（BaseTrendsManagerの共通処理を使用）"""
        logger.debug(f"🔍 はてなブックマーク: get_trends呼び出し (category: {category}, fetch_all_categories: {fetch_all_categories})")
        
        # 全カテゴリを取得する場合（スケジューラー用の特殊ケース）
        if fetch_all_categories:
            logger.info("🔄 はてなブックマーク: 全カテゴリのデータを取得します")
            all_data = self._fetch_and_cache_all_categories()
            if all_data:
                self._save_all_categories_to_cache(all_data)
                # 'all'カテゴリのデータを返す（互換性のため）
                all_category_data = [item for item in all_data if item.get('category') == 'all']
                return {
                    'data': all_category_data[:limit] if all_category_data else [],
                    'status': 'api_fetched',
                    'category': 'all',
                    'source': 'Hatena API',
                    'success': True
                }
            else:
                return {
                    'data': [],
                    'status': 'api_error',
                    'category': 'all',
                    'error': '全カテゴリのデータ取得に失敗しました',
                    'success': False
                }
        
        # BaseTrendsManagerの共通処理を使用
        # auto_fetch_on_cache_miss=Trueで、キャッシュがない場合はAPIを呼び出す（既存動作を維持）
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュがない場合はAPIを呼び出す
            category=category
        )
        
        # categoryパラメータを結果に追加
        if result and isinstance(result, dict):
            result['category'] = category
        logger.debug(f"🔍 はてなブックマーク: get_trends完了 (category: {category})")
        return result
    
    def get_hot_entries(self, category='all', limit=25, force_refresh=False):
        """はてなブックマークのホットエントリーを取得（後方互換性のため、get_trendsを呼び出す）"""
        # 後方互換性のため、get_trendsを呼び出す
        return self.get_trends(category=category, limit=limit, force_refresh=force_refresh)
    
    def get_new_entries(self, category='all', limit=25):
        """はてなブックマークの新着エントリーを取得（公式RSS使用）"""
        try:
            # カテゴリー別新着RSS URLを構築
            if category == 'all':
                rss_url = f"{self.base_url}/hotentry.rss"  # ホットエントリーを使用
            else:
                rss_url = f"{self.base_url}/entrylist/{category}.rss"
            
            logger.info(f"はてなブックマーク新着エントリーRSS取得開始: {rss_url}")
            
            # RSSフィードを取得
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                return {'error': 'RSSフィードからエントリーを取得できませんでした'}
            
            # エントリー情報を抽出
            items = []
            for entry in feed.entries[:limit]:
                # 公開日時を適切にフォーマット
                published = entry.get('published', '') or entry.get('updated', '') or entry.get('created', '')
                if published:
                    try:
                        from datetime import datetime
                        import email.utils
                        # RFC 2822形式の日付をパース
                        parsed_date = email.utils.parsedate_tz(published)
                        if parsed_date:
                            dt = datetime(*parsed_date[:6])
                            published = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        # パースに失敗した場合は元の文字列を使用
                        published = published
                else:
                    # 日付が取得できない場合は現在時刻を使用
                    from datetime import datetime
                    published = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # entry_idを生成（URLのハッシュ化）
                import hashlib
                entry_url = entry.get('link', '')
                entry_id = hashlib.md5(entry_url.encode('utf-8')).hexdigest() if entry_url else ''
                
                item = {
                    'entry_id': entry_id,
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'description': entry.get('summary', ''),
                    'published': published,
                    'author': entry.get('author', ''),
                    'category': category
                }
                
                # ブックマーク数を取得（キャッシュデータの場合はスキップ）
                item['bookmark_count'] = self._get_bookmark_count(item['url'])
                items.append(item)
            
            # ブックマーク数でソート（降順）
            items.sort(key=lambda x: x.get('bookmark_count', 0), reverse=True)
            
            # ランクを付与（ブックマーク数でソート後）
            trends_data = []
            for i, item in enumerate(items):
                trends_data.append({
                    'entry_id': item['entry_id'],
                    'rank': i + 1,
                    'title': item['title'],
                    'url': item['url'],
                    'description': item['description'],
                    'bookmark_count': item['bookmark_count'],
                    'published': item['published'],
                    'author': item['author'],
                    'category': item['category']
                })
            
            return {
                'data': trends_data,
                'status': 'success',
                'source': f'はてなブックマーク新着エントリー（{category}）',
                'total_count': len(trends_data),
                'category': category
            }
                
        except Exception as e:
            import traceback
            error_msg = f'はてなブックマーク新着エントリー取得エラー: {str(e)}'
            logger.error(f"❌ {error_msg}")
            traceback.print_exc()
            return {
                'error': error_msg,
                'data': [],
                'status': 'api_error',
                'success': False
            }
    
    def _get_bookmark_count(self, url):
        """はてなブックマークCount APIでブックマーク数を取得"""
        try:
            params = {'url': url}
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(self.count_api_url, params=params, timeout=5)
            
            if response.status_code == 200:
                # 返り値は数値 or "null"（存在しない場合）
                try:
                    count_text = response.text.strip()
                    if count_text.isdigit():
                        return int(count_text)
                    else:
                        return 0
                except:
                    return 0
            else:
                return 0
                
        except Exception as e:
            logger.error(f"ブックマーク数取得エラー: {e}", exc_info=True)
            return 0
    
    def get_entry_details(self, url):
        """はてなブックマークEntry APIでエントリー詳細を取得"""
        try:
            params = {'url': url}
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(self.entry_api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'title': data.get('title', ''),
                    'url': data.get('url', ''),
                    'bookmarks': data.get('bookmarks', []),
                    'tags': data.get('tags', []),
                    'screenshot': data.get('screenshot', ''),
                    'eid': data.get('eid', '')
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"エントリー詳細取得エラー: {e}", exc_info=True)
            return None
    
    def get_available_categories(self):
        """利用可能なカテゴリー一覧を取得（人気の5カテゴリに絞り込み）"""
        return [
            'all',           # 総合
            'it',            # テクノロジー（最も人気）
            'social',        # ニュース・社会（文化、事件、時事）
            'entertainment', # エンタメ（スポーツ、芸能、音楽、映画）
            'life',          # 暮らし（衣食住、恋愛、人間関係、悩み）
            'knowledge'      # 学び（科学技術、学問、学習）
        ]
    
    def get_hatena_trends_summary(self):
        """はてなブックマークトレンドの概要を取得"""
        return {
            'hatena_api': {
                'available': True,
                'note': 'はてなブックマーク公式RSS + API: ホットエントリー、新着エントリー',
                'features': [
                    'ホットエントリー取得（RSS）',
                    '新着エントリー取得（RSS）',
                    'カテゴリー別分類',
                    'ブックマーク数取得（Count API）',
                    'エントリー詳細取得（Entry API）',
                    '公式API使用（スクレイピングなし）'
                ]
            },
            'limitations': [
                'RSS更新頻度に依存',
                'レート制限あり',
                'カテゴリー数が多い'
            ],
            'setup_required': [
                'feedparserライブラリ',
                '公式RSS + API使用'
            ]
        }
    
    def get_from_cache(self, cache_key):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_from_cache('hatena_trends', 'hatena_trends')
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def get_from_cache_by_category(self, category):
        """カテゴリ別にキャッシュからデータを取得（後方互換性のため、_get_from_cacheを呼び出す）"""
        # 後方互換性のため、_get_from_cacheを呼び出す
        return self._get_from_cache(category=category)
    
    def _fetch_and_cache_all_categories(self):
        """全カテゴリのデータを一度に取得してキャッシュに保存"""
        try:
            logger.info("🔄 はてなブックマーク: 全カテゴリのデータを取得開始")
            
            # 利用可能なカテゴリを取得
            categories = self.get_available_categories()
            all_data = []
            
            for category in categories:
                logger.info(f"📊 カテゴリ '{category}' のデータを取得中...")
                api_result = self.get_new_entries(category, 25)
                logger.debug(f"🔍 カテゴリ '{category}' API結果: {api_result}")
                if api_result and not api_result.get('error'):
                    trends_data = api_result.get('data', [])
                    for item in trends_data:
                        item['category'] = category
                    all_data.extend(trends_data)
                    logger.info(f"✅ カテゴリ '{category}': {len(trends_data)}件取得")
                else:
                    logger.warning(f"❌ カテゴリ '{category}': データ取得失敗 - {api_result}")
            
            # 'all'カテゴリのデータを追加（ホットエントリーから取得）
            logger.info(f"📊 カテゴリ 'all' のデータを取得中...")
            api_result = self.get_new_entries('all', 25)
            if api_result and not api_result.get('error'):
                trends_data = api_result.get('data', [])
                for item in trends_data:
                    item['category'] = 'all'
                all_data.extend(trends_data)
                logger.info(f"✅ カテゴリ 'all': {len(trends_data)}件取得")
            
            # データ取得は成功（保存は呼び出し元で行う）
            if all_data:
                logger.info(f"✅ はてなブックマーク: 全カテゴリのデータ取得完了 ({len(all_data)}件)")
            else:
                logger.warning("❌ はてなブックマーク: 取得したデータがありません")
                
        except Exception as e:
            import traceback
            logger.error(f"❌ 全カテゴリ取得エラー: {e}", exc_info=True)
            traceback.print_exc()
            all_data = []
        
        # 取得したデータを返す（保存処理は呼び出し元で行う）
        return all_data
    
    def _save_all_categories_to_cache(self, all_data):
        """全カテゴリのデータをキャッシュに保存"""
        if not all_data:
            return 0
        
        try:
            # 重複排除
            seen = set()
            unique_data = []
            for item in all_data:
                category = item.get('category', '')
                title = item.get('title', '')
                url = item.get('url', '')
                dedupe_key = (category, title, url)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                unique_data.append(item)
            
            # カテゴリごとにグループ化して保存
            saved_count = 0
            categories = self.get_available_categories()
            for category in categories:
                category_data = [item for item in unique_data if item.get('category') == category]
                if category_data:
                    # 他のカテゴリと同じように、TrendsCacheのメソッドを使用
                    # regionパラメータにcategoryを渡すことで、カテゴリごとに保存
                    success = self.db.save_hatena_trends_to_cache(category_data, category)
                    if success:
                        saved_count += len(category_data)
                        logger.info(f"✅ カテゴリ '{category}': {len(category_data)}件をキャッシュに保存しました")
            
            if saved_count > 0:
                logger.info(f"✅ はてなブックマーク: 全カテゴリのデータをキャッシュに保存完了 ({saved_count}件)")
                # cache_statusを更新
                self._update_cache_status('hatena_trends', saved_count)
            
            return saved_count
            
        except Exception as e:
            logger.error(f"❌ 全カテゴリキャッシュ保存エラー: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return 0
    
    def save_to_cache(self, data, cache_key):
        """データをキャッシュに保存"""
        try:
            # 同一カテゴリ内での重複を排除
            unique_data = []
            seen = set()
            for item in data or []:
                category = item.get('category', cache_key)
                title = item.get('title', '')
                url = item.get('url', '')
                dedupe_key = (category, title, url)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                unique_data.append(item)

            self.db.save_hatena_trends_to_cache(unique_data, cache_key)
            # cache_statusテーブルも更新
            self._update_cache_status('hatena_trends', len(unique_data))
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
    def is_cache_valid(self, cache_key):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_hatena_cache_valid(cache_key)
        except Exception as e:
            logger.error(f"キャッシュ有効性チェックエラー: {e}", exc_info=True)
            return False
    
    def _should_refresh_cache(self, cache_key):
        """今日既にキャッシュを更新したかチェック（朝5時から夜12時まで）"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            today = now.date()
            current_hour = now.hour
            
            # 時間制限：5時から24時まで
            if not (5 <= current_hour < 24):
                logger.info(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            conn = self.db.get_connection()
            if not conn:
                logger.warning("⚠️ データベース接続が取得できませんでした。キャッシュチェックをスキップします")
                return False
            
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('hatena_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
            return True
    
    def _update_refresh_time(self, cache_key):
        """キャッシュ更新日時を記録"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            conn = self.db.get_connection()
            if not conn:
                logger.warning("⚠️ データベース接続が取得できませんでした。更新日時記録をスキップします")
                return
            
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) 
                        DO UPDATE SET 
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('hatena_trends', now, 25))  # 正しいキャッシュキーを使用
                    conn.commit()
        except Exception as e:
            logger.error(f"更新日時記録エラー: {e}", exc_info=True)
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.error(f"cache_status更新エラー: {e}", exc_info=True)
            return False

    def _get_cache_info(self, cache_key):
        """キャッシュ情報を取得"""
        try:
            conn = self.db.get_connection()
            if not conn:
                logger.warning("⚠️ データベース接続が取得できませんでした。キャッシュ情報取得をスキップします")
                return {'last_updated': None, 'data_count': 0}
            
            with conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('hatena_trends',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] or 0
                        }
                    return {'last_updated': None, 'data_count': 0}
        except Exception as e:
            logger.error(f"キャッシュ情報取得エラー: {e}", exc_info=True)
            return {'last_updated': None, 'data_count': 0}