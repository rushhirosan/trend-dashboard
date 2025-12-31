import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class NewsTrendsManager:
    """NewsAPIを使用してニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.api_key = os.getenv('NEWS_API_KEY')
        self.db = TrendsCache()
        # レート制限: News APIは100 requests/日（保守的に10リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('news', max_requests=10, window_seconds=60)
        
        if not self.api_key:
            logger.warning("Warning: NEWS_API_KEYが設定されていません")
        
        logger.debug(f"News API認証情報確認:")
        logger.debug(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
        
        # NewsAPI接続テスト（キャッシュモードでは無効化）
        # if self.api_key:
        #     self._test_connection()
    
    def _test_connection(self):
        """NewsAPI接続テスト"""
        try:
            # 簡単なテストリクエスト
            test_url = f"https://newsapi.org/v2/top-headlines?country=jp&apiKey={self.api_key}"
            response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"News API接続テスト成功: {data.get('totalResults', 0)}件の記事")
                logger.debug(f"レスポンス詳細: {data}")
            else:
                logger.warning(f"News API接続テスト失敗: {response.status_code}")
                logger.warning(f"エラーレスポンス: {response.text}")
                
        except Exception as e:
            logger.error(f"News API接続テストエラー: {e}", exc_info=True)
    
    def get_trends(self, country='jp', category='general', page_size=25, force_refresh=False):
        """ニューストレンドを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            logger.debug(f"🔍 News: キャッシュデータ取得開始 (country: {country}, category: {category})")
            
            cached_data = None
            if force_refresh:
                logger.info(f"🔄 News: force_refresh指定のためキャッシュをスキップします (country: {country}, category: {category})")
            else:
                cached_data = self.get_from_cache(country, category)
                logger.debug(f"🔍 News: キャッシュデータ取得結果: {type(cached_data)}, 長さ: {len(cached_data) if cached_data else 0}")
            
            if cached_data:
                logger.info(f"✅ News: キャッシュデータを使用 ({len(cached_data)}件)")
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'country': country.upper(),
                    'category': category
                }
            # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
            if not force_refresh:
                logger.warning(f"⚠️ News: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません (country: {country}, category: {category})")
                return {
                    'data': [],
                    'status': 'cache_not_found',
                    'country': country.upper(),
                    'category': category,
                    'success': False,
                    'error': 'キャッシュにデータがありません'
                }
            # force_refresh=trueの場合のみ外部APIを呼び出す
            logger.warning(f"⚠️ News: キャッシュ未使用のため外部APIを呼び出します")
            trends_data = self._get_news_trends(country, category, page_size)
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, country, category)
                logger.info(f"✅ News: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                return {
                    'data': trends_data,
                    'status': 'api_fetched',
                    'country': country.upper(),
                    'category': category,
                    'source': 'News API'
                }
            else:
                logger.error(f"❌ News: 外部APIからデータを取得できませんでした")
                return {
                    'data': [],
                    'status': 'api_error',
                    'country': country.upper(),
                    'category': category
                }
                
        except Exception as e:
            logger.error(f"ニューストレンド取得エラー: {e}", exc_info=True)
            return {'error': f'ニューストレンドの取得に失敗しました: {str(e)}'}
    
    def _get_news_trends(self, country='jp', category='general', page_size=25):
        """NewsAPIからトレンドデータを取得"""
        if not self.api_key:
            logger.warning("News APIキーが設定されていません")
            return None
        
        try:
            logger.info(f"News API呼び出し開始 (国: {country}, カテゴリ: {category})")
            
            # 複数の方法で記事を取得しようとする
            trends = []
            
            # 1. カテゴリ付きtop-headlines（複数のカテゴリを試行）
            logger.debug("1. カテゴリ付きtop-headlinesを試行...")
            categories_to_try = ['general', 'business', 'technology', 'entertainment', 'sports']
            for cat in categories_to_try:
                logger.debug(f"   カテゴリ '{cat}' を試行...")
                trends = self._get_news_trends_with_category(country, cat, page_size)
                if trends and len(trends) > 0:
                    logger.info(f"   カテゴリ '{cat}' で記事を取得しました！")
                    break
            
            # 2. カテゴリなしtop-headlines
            if not trends or len(trends) == 0:
                logger.debug("2. カテゴリなしtop-headlinesを試行...")
                trends = self._get_news_trends_without_category(country, page_size)
            
            # 3. 異なる国で試行（JPが指定されている場合はスキップ）
            # JPが指定されている場合、JPのデータのみを取得する（フォールバックで他の国のデータを取得しない）
            if country.lower() != 'jp' and (not trends or len(trends) == 0):
                logger.debug("3. 異なる国で試行...")
                countries_to_try = ['us', 'gb', 'ca', 'au']
                for c in countries_to_try:
                    logger.debug(f"   国 '{c}' を試行...")
                    trends = self._get_news_trends_without_category(c, page_size)
                    if trends and len(trends) > 0:
                        logger.info(f"   国 '{c}' で記事を取得しました！")
                        break
            
            # 4. everythingエンドポイントで検索（JPが指定されている場合はスキップ）
            if country.lower() != 'jp' and (not trends or len(trends) == 0):
                logger.debug("4. everythingエンドポイントで検索を試行...")
                trends = self._get_news_trends_everything(country, page_size)
            
            # 5. サンプルデータ（最後の手段、JPが指定されている場合はスキップ）
            # JPが指定されている場合、サンプルデータを使用しない（空のリストを返す）
            if country.lower() != 'jp' and (not trends or len(trends) == 0):
                logger.warning("5. サンプルデータを生成...")
                trends = self._get_sample_news_data()
            
            return trends
            
        except Exception as e:
            logger.error(f"News API エラー: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
            return None
    
    def _get_news_trends_with_category(self, country='jp', category='general', page_size=25):
        """カテゴリ付きでNewsAPIからトレンドデータを取得"""
        try:
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                'country': country,
                'category': category,
                'pageSize': page_size,
                'apiKey': self.api_key
            }
            
            logger.debug(f"カテゴリ付きリクエスト: {params}")
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"News API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            logger.debug(f"News API レスポンス: {data}")
            
            if data.get('status') != 'ok':
                logger.error(f"News API レスポンスエラー: {data.get('message', 'Unknown error')}")
                return None
            
            articles = data.get('articles', [])
            logger.info(f"カテゴリ '{category}' で取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                return []
            
            trends = []
            for i, article in enumerate(articles, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(articles) - 1)) if len(articles) > 1 else 100
                
                trends.append({
                    'rank': i,
                    'title': article.get('title', 'No Title'),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'url': article.get('url', ''),
                    'image_url': article.get('urlToImage', ''),
                    'published_at': article.get('publishedAt', ''),
                    'score': round(score, 1),
                    'category': category
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"カテゴリ付きNews API エラー: {e}", exc_info=True)
            return []
    
    def _get_news_trends_without_category(self, country='jp', page_size=25):
        """カテゴリなしでNewsAPIからトレンドデータを取得"""
        try:
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                'country': country,
                'pageSize': page_size,
                'apiKey': self.api_key
            }
            
            logger.debug(f"カテゴリなしリクエスト: {params}")
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"News API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            logger.debug(f"News API レスポンス: {data}")
            
            if data.get('status') != 'ok':
                logger.error(f"News API レスポンスエラー: {data.get('message', 'Unknown error')}")
                return None
            
            articles = data.get('articles', [])
            logger.info(f"カテゴリなしで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                logger.warning("カテゴリなしでも記事が取得できませんでした")
                return []
            
            trends = []
            for i, article in enumerate(articles, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(articles) - 1)) if len(articles) > 1 else 100
                
                trends.append({
                    'rank': i,
                    'title': article.get('title', 'No Title'),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'url': article.get('url', ''),
                    'image_url': article.get('urlToImage', ''),
                    'published_at': article.get('publishedAt', ''),
                    'score': round(score, 1),
                    'category': 'general'
                })
            
            logger.info(f"カテゴリなしで処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            logger.error(f"カテゴリなしNews API エラー: {e}", exc_info=True)
            return []
    
    def _get_news_trends_everything(self, country='jp', page_size=25):
        """everythingエンドポイントでNewsAPIからトレンドデータを取得"""
        try:
            url = "https://newsapi.org/v2/everything"
            
            # 国別の検索クエリを設定
            country_queries = {
                'jp': 'japan OR 日本 OR 東京 OR 大阪',
                'us': 'united states OR USA OR America',
                'gb': 'united kingdom OR UK OR Britain'
            }
            
            query = country_queries.get(country.lower(), 'news')
            
            params = {
                'q': query,
                'language': 'en' if country.lower() != 'jp' else 'en,ja',
                'sortBy': 'publishedAt',
                'pageSize': page_size,
                'apiKey': self.api_key
            }
            
            logger.debug(f"everythingエンドポイントリクエスト: {params}")
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"News API everything エラー: HTTP {response.status_code}")
                return []
            
            data = response.json()
            logger.debug(f"News API everything レスポンス: {data}")
            
            if data.get('status') != 'ok':
                logger.error(f"News API everything レスポンスエラー: {data.get('message', 'Unknown error')}")
                return []
            
            articles = data.get('articles', [])
            logger.info(f"everythingエンドポイントで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                logger.warning("everythingエンドポイントでも記事が取得できませんでした")
                return []
            
            trends = []
            for i, article in enumerate(articles, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(articles) - 1)) if len(articles) > 1 else 100
                
                trends.append({
                    'rank': i,
                    'title': article.get('title', 'No Title'),
                    'description': article.get('description', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'url': article.get('url', ''),
                    'image_url': article.get('urlToImage', ''),
                    'published_at': article.get('publishedAt', ''),
                    'score': round(score, 1),
                    'category': 'general'
                })
            
            logger.info(f"everythingエンドポイントで処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            logger.error(f"everythingエンドポイントNews API エラー: {e}", exc_info=True)
            return []
    
    def _get_sample_news_data(self):
        """サンプルのニュースデータを生成（テスト用）"""
        logger.warning("サンプルニュースデータを生成します")
        
        sample_news = [
            {
                'rank': 1,
                'title': 'AI技術の最新動向と将来展望',
                'description': '人工知能技術の最新の進歩と、今後の発展方向性について',
                'source': 'Tech News Japan',
                'url': 'https://example.com/ai-news-1',
                'image_url': '',
                'published_at': '2025-08-28T10:00:00Z',
                'score': 100.0,
                'category': 'technology'
            },
            {
                'rank': 2,
                'title': '持続可能なエネルギー政策の推進',
                'description': '再生可能エネルギーを中心とした環境配慮型のエネルギー戦略',
                'source': 'Environment Daily',
                'url': 'https://example.com/energy-news-1',
                'image_url': '',
                'published_at': '2025-08-28T09:30:00Z',
                'score': 95.0,
                'category': 'environment'
            },
            {
                'rank': 3,
                'title': 'グローバル経済の新たな潮流',
                'description': '世界経済における最新のトレンドと市場動向の分析',
                'source': 'Global Finance',
                'url': 'https://example.com/economy-news-1',
                'image_url': '',
                'published_at': '2025-08-28T09:00:00Z',
                'score': 90.0,
                'category': 'business'
            },
            {
                'rank': 4,
                'title': '健康とウェルネスの最新研究',
                'description': '科学的根拠に基づく健康維持と生活習慣改善の方法',
                'source': 'Health Science',
                'url': 'https://example.com/health-news-1',
                'image_url': '',
                'published_at': '2025-08-28T08:30:00Z',
                'score': 85.0,
                'category': 'health'
            },
            {
                'rank': 5,
                'title': 'デジタル変革の加速',
                'description': '企業のデジタル化推進とDX戦略の最新事例',
                'source': 'Digital Times',
                'url': 'https://example.com/digital-news-1',
                'image_url': '',
                'published_at': '2025-08-28T08:00:00Z',
                'score': 80.0,
                'category': 'technology'
            }
        ]
        
        logger.info(f"サンプルニュースデータ生成完了: {len(sample_news)}件")
        return sample_news
    
    def get_from_cache(self, country, category):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_news_trends_from_cache(country, category)
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def save_to_cache(self, data, country, category):
        """データをキャッシュに保存"""
        try:
            self.db.save_news_trends_to_cache(data, country, category)
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
    def is_cache_valid(self, country, category):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_news_cache_valid(country, category)
        except Exception as e:
            logger.error(f"キャッシュ有効性チェックエラー: {e}", exc_info=True)
            return False 