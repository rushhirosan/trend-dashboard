import gc
import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

logger = get_logger(__name__)


class NoteTrendsManager(BaseTrendsManager):
    """note.com トレンド管理クラス（RSSフィード使用、カテゴリ対応）"""

    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='note', max_requests=10, window_seconds=60)
        
        # カテゴリ別RSSフィードURL
        self.category_urls = {
            'all': 'https://note.com/rss',
            'tech': 'https://note.com/categories/tech/rss',
            'business': 'https://note.com/categories/business/rss',
            'lifestyle': 'https://note.com/categories/lifestyle/rss',
            'entertainment': 'https://note.com/categories/entertainment/rss',
        }

        logger.info("Note Trends Manager初期化:")
        logger.info(f"  カテゴリ: {list(self.category_urls.keys())}")

    def get_available_categories(self):
        """利用可能なカテゴリー一覧を取得"""
        return [
            'all',           # 総合
            'tech',          # テクノロジー
            'business',      # ビジネス
            'lifestyle',     # ライフスタイル
            'entertainment', # エンタメ
        ]

    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        return 'note_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        category = kwargs.get('category', 'all')
        cached_data = self.db.get_note_trends_from_cache(category)
        if cached_data:
            # カテゴリでフィルタリング
            category_data = [item for item in cached_data if item.get('category') == category]
            return category_data
        return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            category = kwargs.get('category', 'all')
            return self.db.save_note_trends_to_cache(data, category)
        except Exception as e:
            logger.error(f"❌ Note キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            category = kwargs.get('category', 'all')
            return self.db.clear_note_trends_cache(category)
        except Exception as e:
            logger.error(f"❌ Note キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新"""
        try:
            category = kwargs.get('category', 'all')
            cache_key_with_category = f'{cache_key}_{category}'
            return self.db.update_cache_status(cache_key_with_category, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Note: cache_status更新エラー: {e}")
            return False

    def get_trends(self, category='all', limit=25, force_refresh=False, fetch_all_categories=False):
        """Noteトレンドを取得（キャッシュ優先）"""
        # ダミーモード時は fetch_all_categories でもベースクラスのダミー処理を使用（実API呼び出しを回避）
        if fetch_all_categories and self._is_dummy_mode():
            return super().get_trends(
                limit=limit,
                force_refresh=force_refresh,
                auto_fetch_on_cache_miss=True,
                sort_key='published_date',
                sort_reverse=True,
                category=category
            )
        
        # 全カテゴリを取得する場合
        if fetch_all_categories:
            logger.info("🔄 Note: 全カテゴリのデータを取得します")
            all_rows, any_saved = self._fetch_and_cache_all_categories()
            if any_saved:
                return {
                    'data': all_rows[:limit] if all_rows else [],
                    'status': 'api_fetched',
                    'category': 'all',
                    'source': 'Note RSS',
                    'success': True
                }
            return {
                'data': [],
                'status': 'api_error',
                'category': 'all',
                'error': '全カテゴリのデータ取得に失敗しました',
                'success': False
            }

        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Trueで、キャッシュがない場合はAPIを呼び出す（はてぶと同じ挙動）
        # sort_key='published_date'で公開日でソート
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュがない場合はAPIを呼び出す
            sort_key='published_date',  # 公開日でソート
            sort_reverse=True,  # 降順（新しい順）
            category=category
        )
        # categoryパラメータを結果に追加
        if result and isinstance(result, dict):
            result['category'] = category
        return result

    def _fetch_trends(self, category='all', limit=25, *args, **kwargs):
        """Note RSSフィードからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            rss_url = self.category_urls.get(category, self.category_urls['all'])
            logger.info(f"Note RSS呼び出し開始: {rss_url} (category: {category})")
            
            feed = feedparser.parse(rss_url)
            
            if not feed.entries:
                logger.warning(f"⚠️ Note RSS: エントリーが見つかりませんでした (category: {category})")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'category': category,
                    'source': 'note_rss'
                }

            logger.info(f"✅ Note RSS: {len(feed.entries)}件のエントリーを取得 (category: {category})")

            formatted_data = []
            for entry in feed.entries[:limit]:
                try:
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_date = datetime(*entry.published_parsed[:6])
                        except Exception:
                            published_date = datetime.now()
                    elif hasattr(entry, 'published'):
                        try:
                            from email.utils import parsedate_to_datetime
                            published_date = parsedate_to_datetime(entry.published)
                        except Exception:
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()

                    description = ''
                    if hasattr(entry, 'description'):
                        description = entry.description
                    elif hasattr(entry, 'summary'):
                        description = entry.summary

                    formatted_data.append({
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('link', ''),
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description,
                        'author': entry.get('author', ''),
                        'category': category,
                        'source': 'Note'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Note エントリーパースエラー: {e}")
                    continue

            formatted_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
            for i, item in enumerate(formatted_data, 1):
                item['rank'] = i
            final_data = formatted_data[:limit]

            logger.info(f"✅ Note: {len(final_data)}件の記事を取得しました (category: {category})")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'category': category,
                'source': 'note_rss',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Note RSS タイムアウトエラー", exc_info=True)
            return {'error': 'Note RSS タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Note RSS エラー: {e}", exc_info=True)
            return {'error': f'Note RSS取得エラー: {str(e)}', 'success': False}

    def _dedupe_note_items(self, items):
        seen = set()
        out = []
        for item in items or []:
            key = (item.get('title', ''), item.get('url', ''))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _fetch_and_cache_all_categories(self):
        """全カテゴリを順に取得し、カテゴリごとにキャッシュへ保存（ピークメモリ抑制）"""
        all_rows_for_all = []
        any_saved = False
        total_saved = 0
        try:
            logger.info("🔄 Note: 全カテゴリのデータを取得開始")
            categories = self.get_available_categories()

            for category in categories:
                logger.info(f"📊 Note カテゴリ '{category}' のデータを取得中...")
                result = self._fetch_trends(category, 25)
                if not result.get('success') or not result.get('data'):
                    logger.warning(f"❌ Note カテゴリ '{category}': データ取得失敗")
                    gc.collect()
                    continue
                trends_data = result.get('data', [])
                for item in trends_data:
                    item['category'] = category
                unique = self._dedupe_note_items(trends_data)
                if not unique:
                    gc.collect()
                    continue
                if self.db.save_note_trends_to_cache(unique, category):
                    any_saved = True
                    total_saved += len(unique)
                    logger.info(f"✅ Note カテゴリ '{category}': {len(unique)}件取得・キャッシュ保存")
                if category == 'all':
                    all_rows_for_all = list(unique)
                gc.collect()

            if any_saved and total_saved > 0:
                logger.info(f"✅ Note: 全カテゴリのデータ取得・保存完了 ({total_saved}件)")
            elif not any_saved:
                logger.warning("❌ Note: 取得したデータがありません")
        except Exception as e:
            logger.error(f"❌ Note 全カテゴリ取得エラー: {e}", exc_info=True)
            any_saved = False

        return all_rows_for_all, any_saved

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
                    success = self.db.save_note_trends_to_cache(category_data, category)
                    if success:
                        saved_count += len(category_data)
                        logger.info(f"✅ Note カテゴリ '{category}': {len(category_data)}件をキャッシュに保存しました")
            
            if saved_count > 0:
                logger.info(f"✅ Note: 全カテゴリのデータをキャッシュに保存完了 ({saved_count}件)")
            
            return saved_count
            
        except Exception as e:
            logger.error(f"❌ Note 全カテゴリキャッシュ保存エラー: {e}", exc_info=True)
            return 0
