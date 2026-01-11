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
        # カテゴリー別RSS URLを環境変数から取得（AmaranRSSなどで生成したRSS URL）
        # カテゴリーごとに個別の環境変数を設定可能
        self.rss_urls_by_category = {
            'books': os.getenv('AMAZON_RSS_URL_BOOKS', '').strip(),
            'electronics': os.getenv('AMAZON_RSS_URL_ELECTRONICS', '').strip(),
            'computers': os.getenv('AMAZON_RSS_URL_COMPUTERS', '').strip(),
        }
        
        # 空の環境変数をフィルタリング
        self.rss_urls_by_category = {
            category: url for category, url in self.rss_urls_by_category.items() if url
        }
        
        # 後方互換性のため、AMAZON_RSS_URLS（カンマ区切り）もサポート
        rss_urls_env = os.getenv('AMAZON_RSS_URLS', '').strip()
        if rss_urls_env and not self.rss_urls_by_category:
            # カンマ区切りで分割し、順番にbooks, electronics, computersに割り当て
            urls = [url.strip() for url in rss_urls_env.split(',') if url.strip()]
            categories = ['books', 'electronics', 'computers']
            for i, url in enumerate(urls):
                if i < len(categories):
                    self.rss_urls_by_category[categories[i]] = url
        
        if not self.rss_urls_by_category:
            logger.warning("⚠️ Amazon RSS URL環境変数が設定されていません。AmaranRSS等で生成したRSS URLを設定してください。")
        
        self.db = TrendsCache()
        # レート制限: AmaranRSSの推奨に従い、1時間に1回（3600秒）に設定
        self.rate_limiter = get_rate_limiter('amazon', max_requests=1, window_seconds=3600)

        logger.info("Amazon Best Sellers Trends Manager初期化:")
        logger.info(f"  カテゴリー別RSS URLs: {self.rss_urls_by_category if self.rss_urls_by_category else '(未設定)'}")
        
        # 利用可能なカテゴリー一覧を取得する関数
        self.available_categories = list(self.rss_urls_by_category.keys()) if self.rss_urls_by_category else []

    def get_trends(self, category='books', limit=25, force_refresh=False):
        """Amazon Best Sellersトレンドを取得（キャッシュ優先）
        
        Args:
            category (str): カテゴリー ('books', 'electronics', 'computers')
            limit (int): 取得件数
            force_refresh (bool): キャッシュを無視して取得するかどうか
        """
        try:
            # カテゴリーのバリデーション
            if category not in self.rss_urls_by_category:
                available = ', '.join(self.available_categories) if self.available_categories else '(なし)'
                error_msg = f"カテゴリー '{category}' は利用できません。利用可能なカテゴリー: {available}"
                logger.warning(f"⚠️ Amazon: {error_msg}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'invalid_category',
                    'error': error_msg,
                    'available_categories': self.available_categories
                }
            
            if force_refresh:
                logger.info(f"🔄 Amazon ({category}) force_refresh: キャッシュをクリアします")
                self.db.clear_amazon_trends_cache()

            cached_data = self.db.get_amazon_trends_from_cache(category)
            if cached_data:
                # カテゴリーでフィルタリング（データにcategoryフィールドがある場合）
                filtered_data = [item for item in cached_data if item.get('category') == category]
                if not filtered_data:
                    # categoryフィールドがない場合は全データを使用（後方互換性）
                    filtered_data = cached_data
                
                # ランキングでソート（昇順）
                filtered_data.sort(key=lambda x: x.get('rank', 999), reverse=False)
                logger.info(f"✅ Amazon ({category}): キャッシュから{len(filtered_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': filtered_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'category': category
                }
            else:
                if not force_refresh:
                    logger.warning(f"⚠️ Amazon ({category}): キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    # カテゴリーが利用可能かチェック
                    category_available = category in self.rss_urls_by_category
                    return {
                        'success': True,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'category': category,
                        'category_available': category_available,
                        'available_categories': self.available_categories,
                        'message': 'キャッシュにデータがありません。force_refresh=trueで更新してください。'
                    }
                logger.warning(f"⚠️ Amazon ({category}): キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_amazon_trends(category, limit)

        except Exception as e:
            logger.error(f"❌ Amazon トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Amazon Best Sellersトレンドの取得に失敗しました: {str(e)}', 'success': False}

    def get_available_categories(self):
        """利用可能なカテゴリー一覧を取得"""
        return self.available_categories if self.available_categories else []
    
    def _fetch_amazon_trends(self, category='books', limit=25):
        """Amazon Best Sellers RSSフィードからトレンドデータを取得（非公式RSS：AmaranRSS等）
        
        Args:
            category (str): カテゴリー ('books', 'electronics', 'computers')
            limit (int): 取得件数
        """
        try:
            rss_url = self.rss_urls_by_category.get(category)
            if not rss_url:
                logger.warning(f"⚠️ Amazon Best Sellers ({category}): RSS URLが設定されていません。環境変数を設定してください。")
                return {
                    'success': True,
                    'data': [],
                    'status': 'rss_url_not_configured',
                    'source': 'amazon_rss',
                    'category': category,
                    'error': f'RSS URLが設定されていません。{category}用の環境変数を設定してください。'
                }
            
            self.rate_limiter.wait_if_needed()

            all_entries = []
            try:
                logger.info(f"Amazon Best Sellers RSS呼び出し開始 ({category}): {rss_url}")
                
                # requestsでタイムアウトを設定して取得
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(rss_url, headers=headers, timeout=10)
                logger.info(f"📊 Amazon RSS({category}): HTTP status={response.status_code}")
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ Amazon RSS({category}): HTTP {response.status_code} - {response.text[:200]}")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'rss_fetch_failed',
                        'source': 'amazon_rss',
                        'category': category,
                        'error': f'RSS取得に失敗しました: HTTP {response.status_code}'
                    }
                
                # AmaranRSSのエラーチェック（エラーコード009, 003など）
                response_text = response.text
                if 'ERROR:Failed to get Amazon bestsellers data' in response_text:
                    # エラーコードを抽出（code:003, code:009など）
                    error_code = 'unknown'
                    if 'code:003' in response_text:
                        error_code = '003'
                    elif 'code:009' in response_text:
                        error_code = '009'
                    elif 'code:' in response_text:
                        # その他のエラーコードを抽出
                        import re
                        match = re.search(r'code:(\d+)', response_text)
                        if match:
                            error_code = match.group(1)
                    
                    logger.warning(f"⚠️ Amazon RSS({category}): AmaranRSSエラーコード{error_code} - Amazon.comのベストセラー情報を取得できませんでした")
                    return {
                        'success': True,
                        'data': [],
                        'status': 'amaranrss_error',
                        'source': 'amazon_rss',
                        'category': category,
                        'error': f'AmaranRSSがAmazon.comのベストセラー情報を取得できませんでした（エラーコード{error_code}）。しばらく待ってから再試行してください。'
                    }
                
                # feedparserで解析
                feed = feedparser.parse(response.content)
                logger.info(f"📊 Amazon RSS({category}): feed status={feed.get('status', 'N/A')}, bozo={feed.get('bozo', False)}, bozo_exception={str(feed.get('bozo_exception', None))[:100] if feed.get('bozo_exception') else None}")
                
                if feed.entries:
                    logger.info(f"✅ Amazon RSS({category}): {len(feed.entries)}件のエントリーを取得")
                    if len(feed.entries) > 0:
                        logger.debug(f"📋 最初のエントリー: {feed.entries[0].get('title', 'N/A')}")
                    all_entries.extend(feed.entries)
                else:
                    logger.warning(f"⚠️ Amazon RSS({category}): エントリーが空です。feed keys: {list(feed.keys())[:5]}")
                    if hasattr(feed, 'feed') and feed.feed:
                        logger.info(f"📋 feed.feed keys: {list(feed.feed.keys())[:5]}")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"❌ Amazon RSS({category}) タイムアウト（10秒）")
                return {
                    'success': True,
                    'data': [],
                    'status': 'timeout',
                    'source': 'amazon_rss',
                    'category': category,
                    'error': 'RSS取得タイムアウト'
                }
            except requests.exceptions.RequestException as e:
                logger.warning(f"❌ Amazon RSS({category}) リクエストエラー: {e}")
                return {
                    'success': True,
                    'data': [],
                    'status': 'request_error',
                    'source': 'amazon_rss',
                    'category': category,
                    'error': f'RSSリクエストエラー: {str(e)}'
                }
            except Exception as e:
                logger.warning(f"❌ Amazon RSS({category}) エラー: {e}", exc_info=True)
                return {
                    'success': True,
                    'data': [],
                    'status': 'error',
                    'source': 'amazon_rss',
                    'category': category,
                    'error': f'RSS取得エラー: {str(e)}'
                }

            logger.info(f"📊 Amazon RSS ({category}) 合計エントリー数: {len(all_entries)}")
            if not all_entries:
                logger.warning(f"⚠️ Amazon Best Sellers ({category}): エントリーを取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_entries',
                    'source': 'amazon_rss',
                    'category': category
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
                        'source': 'Amazon Best Sellers',
                        'category': category  # カテゴリー情報を追加
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Amazon エントリーパースエラー: {e}")
                    continue

            final_data = formatted_data[:limit]

            if final_data:
                self.db.save_amazon_trends_to_cache(final_data)
                self.db.update_cache_status('amazon_trends', len(final_data))

            logger.info(f"✅ Amazon ({category}): {len(final_data)}件のベストセラーを取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'amazon_rss',
                'category': category,
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ Amazon RSS タイムアウトエラー", exc_info=True)
            return {'error': 'Amazon RSS タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ Amazon RSS エラー: {e}", exc_info=True)
            return {'error': f'Amazon RSS取得エラー: {str(e)}', 'success': False}

