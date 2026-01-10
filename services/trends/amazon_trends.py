import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class AmazonTrendsManager:
    """Amazon Best Sellersトレンド管理クラス（RSSフィード使用）"""

    def __init__(self):
        """初期化"""
        # Amazon Best Sellers RSSフィードURL（書籍カテゴリ）
        self.rss_urls = [
            "https://www.amazon.com/gp/rss/bestsellers/books",
            "https://www.amazon.com/gp/rss/bestsellers/electronics",
            "https://www.amazon.com/gp/rss/bestsellers/computers",
        ]
        self.db = TrendsCache()
        # レート制限: RSSフィードは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('amazon', max_requests=10, window_seconds=60)

        logger.info("Amazon Best Sellers Trends Manager初期化:")
        logger.info(f"  RSS URLs: {self.rss_urls}")

    def get_trends(self, limit=25, force_refresh=False):
        """Amazon Best Sellersトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info("🔄 Amazon force_refresh: キャッシュをクリアします")
                self.db.clear_amazon_trends_cache()

            cached_data = self.db.get_amazon_trends_from_cache()
            if cached_data:
                # ランキングでソート（昇順）
                cached_data.sort(key=lambda x: x.get('rank', 999), reverse=False)
                logger.info(f"✅ Amazon: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                if not force_refresh:
                    logger.warning("⚠️ Amazon: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache'
                    }
                logger.warning("⚠️ Amazon: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_amazon_trends(limit)

        except Exception as e:
            logger.error(f"❌ Amazon トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Amazon Best Sellersトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def _fetch_amazon_trends(self, limit=25):
        """Amazon Best Sellers RSSフィードからトレンドデータを取得"""
        try:
            self.rate_limiter.wait_if_needed()

            all_entries = []
            for rss_url in self.rss_urls:
                try:
                    logger.info(f"Amazon Best Sellers RSS呼び出し開始: {rss_url}")
                    feed = feedparser.parse(rss_url)
                    if feed.entries:
                        all_entries.extend(feed.entries)
                        logger.info(f"✅ Amazon RSS({rss_url}): {len(feed.entries)}件のエントリーを取得")
                except requests.exceptions.Timeout:
                    logger.warning(f"❌ Amazon RSS({rss_url}) タイムアウト")
                except Exception as e:
                    logger.warning(f"❌ Amazon RSS({rss_url}) エラー: {e}")

            if not all_entries:
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'amazon_rss'
                }

            # 重複を除去（タイトルベース）
            seen_titles = set()
            unique_entries = []
            for entry in all_entries:
                title = entry.get('title', '').strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    unique_entries.append(entry)

            formatted_data = []
            for i, entry in enumerate(unique_entries[:limit], 1):
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

                    # Amazon URLからASINを抽出（可能な場合）
                    asin = None
                    link = entry.get('link', '')
                    if '/dp/' in link:
                        try:
                            asin = link.split('/dp/')[1].split('/')[0].split('?')[0]
                        except Exception:
                            pass

                    formatted_data.append({
                        'rank': i,
                        'title': entry.get('title', 'No Title'),
                        'url': link,
                        'asin': asin,
                        'published_date': published_date.isoformat() if published_date else None,
                        'description': description[:200] if description else '',  # 説明は200文字に制限
                        'source': 'Amazon Best Sellers'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Amazon エントリーパースエラー: {e}")
                    continue

            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_amazon_trends_to_cache(final_data)
                self.db.update_cache_status('amazon_trends', len(final_data))

            logger.info(f"✅ Amazon: {len(final_data)}件のベストセラーを取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'amazon_rss',
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Amazon RSS タイムアウトエラー", exc_info=True)
            return {'error': 'Amazon RSS タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Amazon RSS エラー: {e}", exc_info=True)
            return {'error': f'Amazon RSS取得エラー: {str(e)}', 'success': False}

