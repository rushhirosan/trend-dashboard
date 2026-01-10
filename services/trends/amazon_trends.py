import os
import feedparser
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class AmazonTrendsManager:
    """Amazon Best Sellersトレンド管理クラス（非公式RSSフィード使用：AmaranRSS等）"""

    def __init__(self):
        """初期化"""
        # 環境変数からRSS URLを取得（AmaranRSSなどで生成したRSS URL）
        # 複数のRSS URLをカンマ区切りで指定可能
        rss_urls_env = os.getenv('AMAZON_RSS_URLS', '').strip()
        
        if rss_urls_env:
            # カンマ区切りで分割し、空白を削除
            self.rss_urls = [url.strip() for url in rss_urls_env.split(',') if url.strip()]
        else:
            # 環境変数が設定されていない場合は空のリスト
            self.rss_urls = []
            logger.warning("⚠️ AMAZON_RSS_URLS環境変数が設定されていません。AmaranRSS等で生成したRSS URLを設定してください。")
        
        self.db = TrendsCache()
        # レート制限: AmaranRSSの推奨に従い、1時間に1回（3600秒）に設定
        self.rate_limiter = get_rate_limiter('amazon', max_requests=1, window_seconds=3600)

        logger.info("Amazon Best Sellers Trends Manager初期化:")
        logger.info(f"  RSS URLs: {self.rss_urls if self.rss_urls else '(未設定 - AMAZON_RSS_URLS環境変数を設定してください)'}")

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
        """Amazon Best Sellers RSSフィードからトレンドデータを取得（非公式RSS：AmaranRSS等）"""
        try:
            if not self.rss_urls:
                logger.warning("⚠️ Amazon Best Sellers: RSS URLが設定されていません。AMAZON_RSS_URLS環境変数を設定してください。")
                return {
                    'success': True,
                    'data': [],
                    'status': 'rss_url_not_configured',
                    'source': 'amazon_rss',
                    'error': 'RSS URLが設定されていません。AMAZON_RSS_URLS環境変数を設定してください。'
                }
            
            self.rate_limiter.wait_if_needed()

            all_entries = []
            for rss_url in self.rss_urls:
                try:
                    logger.info(f"Amazon Best Sellers RSS呼び出し開始: {rss_url}")
                    
                    # requestsでタイムアウトを設定して取得
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    response = requests.get(rss_url, headers=headers, timeout=10)
                    logger.info(f"📊 Amazon RSS({rss_url}): HTTP status={response.status_code}")
                    
                    if response.status_code != 200:
                        logger.warning(f"⚠️ Amazon RSS({rss_url}): HTTP {response.status_code} - {response.text[:200]}")
                        continue
                    
                    # feedparserで解析
                    feed = feedparser.parse(response.content)
                    logger.info(f"📊 Amazon RSS({rss_url}): feed status={feed.get('status', 'N/A')}, bozo={feed.get('bozo', False)}, bozo_exception={str(feed.get('bozo_exception', None))[:100] if feed.get('bozo_exception') else None}")
                    
                    if feed.entries:
                        logger.info(f"✅ Amazon RSS({rss_url}): {len(feed.entries)}件のエントリーを取得")
                        if len(feed.entries) > 0:
                            logger.debug(f"📋 最初のエントリー: {feed.entries[0].get('title', 'N/A')}")
                        all_entries.extend(feed.entries)
                    else:
                        logger.warning(f"⚠️ Amazon RSS({rss_url}): エントリーが空です。feed keys: {list(feed.keys())[:5]}")
                        if hasattr(feed, 'feed') and feed.feed:
                            logger.info(f"📋 feed.feed keys: {list(feed.feed.keys())[:5]}")
                except requests.exceptions.Timeout:
                    logger.warning(f"❌ Amazon RSS({rss_url}) タイムアウト（10秒）")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"❌ Amazon RSS({rss_url}) リクエストエラー: {e}")
                except Exception as e:
                    logger.warning(f"❌ Amazon RSS({rss_url}) エラー: {e}", exc_info=True)

            logger.info(f"📊 Amazon RSS 合計エントリー数: {len(all_entries)}")
            if not all_entries:
                logger.warning(f"⚠️ Amazon Best Sellers: すべてのRSSフィードからエントリーを取得できませんでした")
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

