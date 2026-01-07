import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class NoteTrendsManager:
    """note.com トレンド管理クラス（RSSフィード使用、カテゴリ対応）"""

    def __init__(self):
        """初期化"""
        # カテゴリ別RSSフィードURL
        self.category_urls = {
            'all': 'https://note.com/rss',
            'tech': 'https://note.com/categories/tech/rss',
            'business': 'https://note.com/categories/business/rss',
            'lifestyle': 'https://note.com/categories/lifestyle/rss',
            'entertainment': 'https://note.com/categories/entertainment/rss',
        }
        self.db = TrendsCache()
        self.rate_limiter = get_rate_limiter('note', max_requests=10, window_seconds=60)

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

    def get_trends(self, category='all', limit=25, force_refresh=False, fetch_all_categories=False):
        """Noteトレンドを取得（キャッシュ優先）"""
        try:
            # 全カテゴリを取得する場合
            if fetch_all_categories:
                logger.info("🔄 Note: 全カテゴリのデータを取得します")
                all_data = self._fetch_and_cache_all_categories()
                if all_data:
                    self._save_all_categories_to_cache(all_data)
                    # 'all'カテゴリのデータを返す（互換性のため）
                    all_category_data = [item for item in all_data if item.get('category') == 'all']
                    return {
                        'data': all_category_data[:limit] if all_category_data else [],
                        'status': 'api_fetched',
                        'category': 'all',
                        'source': 'Note RSS',
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

            if force_refresh:
                logger.info(f"🔄 Note force_refresh: カテゴリ '{category}' のキャッシュをクリアします")
                self.db.clear_note_trends_cache(category)

            # カテゴリ別キャッシュから取得
            cached_data = self.db.get_note_trends_from_cache(category)
            
            if cached_data and len(cached_data) > 0:
                # カテゴリでフィルタリング
                category_data = [item for item in cached_data if item.get('category') == category]
                if category_data:
                    category_data.sort(key=lambda x: x.get('published_date') or '', reverse=True)
                    for i, item in enumerate(category_data, 1):
                        item['rank'] = i
                    logger.info(f"✅ Note: キャッシュから{len(category_data)}件のデータを取得しました (category: {category})")
                    return {
                        'success': True,
                        'data': category_data[:limit],
                        'status': 'cached',
                        'category': category,
                        'source': 'database_cache'
                    }
            
            # キャッシュがない場合
            if not force_refresh:
                # force_refresh=Falseでもキャッシュがない場合は外部APIを呼び出す（はてぶと同じ挙動）
                logger.warning(f"⚠️ Note: キャッシュにデータがありません。外部APIを呼び出してデータを取得します (category: {category})")
            
            return self._fetch_note_trends(category, limit)

        except Exception as e:
            logger.error(f"❌ Note トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Noteトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def _fetch_note_trends(self, category='all', limit=25):
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
            for i, entry in enumerate(feed.entries[:limit], 1):
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
                        'rank': i,
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

            if final_data:
                # カテゴリ別にキャッシュに保存
                self.db.save_note_trends_to_cache(final_data, category)
                self.db.update_cache_status(f'note_trends_{category}', len(final_data))

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

    def _fetch_and_cache_all_categories(self):
        """全カテゴリのデータを一度に取得"""
        try:
            logger.info("🔄 Note: 全カテゴリのデータを取得開始")
            
            categories = self.get_available_categories()
            all_data = []
            
            for category in categories:
                logger.info(f"📊 Note カテゴリ '{category}' のデータを取得中...")
                result = self._fetch_note_trends(category, 25)
                if result.get('success') and result.get('data'):
                    trends_data = result.get('data', [])
                    for item in trends_data:
                        item['category'] = category
                    all_data.extend(trends_data)
                    logger.info(f"✅ Note カテゴリ '{category}': {len(trends_data)}件取得")
                else:
                    logger.warning(f"❌ Note カテゴリ '{category}': データ取得失敗")
            
            if all_data:
                logger.info(f"✅ Note: 全カテゴリのデータ取得完了 ({len(all_data)}件)")
            else:
                logger.warning("❌ Note: 取得したデータがありません")
                
        except Exception as e:
            logger.error(f"❌ Note 全カテゴリ取得エラー: {e}", exc_info=True)
            all_data = []
        
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
