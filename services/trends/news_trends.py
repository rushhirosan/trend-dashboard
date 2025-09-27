import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache

class NewsTrendsManager:
    """NewsAPIを使用してニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.api_key = os.getenv('NEWS_API_KEY')
        self.db = TrendsCache()
        
        if not self.api_key:
            print("Warning: NEWS_API_KEYが設定されていません")
        
        print(f"News API認証情報確認:")
        print(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
        
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
                print(f"News API接続テスト成功: {data.get('totalResults', 0)}件の記事")
                print(f"レスポンス詳細: {data}")
            else:
                print(f"News API接続テスト失敗: {response.status_code}")
                print(f"エラーレスポンス: {response.text}")
                
        except Exception as e:
            print(f"News API接続テストエラー: {e}")
    
    def get_trends(self, country='jp', category='general', page_size=25):
        """ニューストレンドを取得"""
        try:
            # キャッシュチェック
            if self.is_cache_valid(country, category):
                cached_data = self.get_from_cache(country, category)
                if cached_data:
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'country': country.upper(),
                        'category': category
                    }
            
            # 新しいデータを取得
            trends_data = self._get_news_trends(country, category, page_size)
            
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, country, category)
                return {
                    'data': trends_data,
                    'status': 'fresh',
                    'country': country.upper(),
                    'category': category
                }
            else:
                return {'error': 'NewsAPIからデータを取得できませんでした。API認証情報を確認してください。'}
                
        except Exception as e:
            print(f"ニューストレンド取得エラー: {e}")
            return {'error': f'ニューストレンドの取得に失敗しました: {str(e)}'}
    
    def _get_news_trends(self, country='jp', category='general', page_size=25):
        """NewsAPIからトレンドデータを取得"""
        if not self.api_key:
            print("News APIキーが設定されていません")
            return None
        
        try:
            print(f"News API呼び出し開始 (国: {country}, カテゴリ: {category})")
            
            # 複数の方法で記事を取得しようとする
            trends = []
            
            # 1. カテゴリ付きtop-headlines（複数のカテゴリを試行）
            print("1. カテゴリ付きtop-headlinesを試行...")
            categories_to_try = ['general', 'business', 'technology', 'entertainment', 'sports']
            for cat in categories_to_try:
                print(f"   カテゴリ '{cat}' を試行...")
                trends = self._get_news_trends_with_category(country, cat, page_size)
                if trends and len(trends) > 0:
                    print(f"   カテゴリ '{cat}' で記事を取得しました！")
                    break
            
            # 2. カテゴリなしtop-headlines
            if not trends or len(trends) == 0:
                print("2. カテゴリなしtop-headlinesを試行...")
                trends = self._get_news_trends_without_category(country, page_size)
            
            # 3. 異なる国で試行
            if not trends or len(trends) == 0:
                print("3. 異なる国で試行...")
                countries_to_try = ['us', 'gb', 'ca', 'au']
                for c in countries_to_try:
                    print(f"   国 '{c}' を試行...")
                    trends = self._get_news_trends_without_category(c, page_size)
                    if trends and len(trends) > 0:
                        print(f"   国 '{c}' で記事を取得しました！")
                        break
            
            # 4. everythingエンドポイントで検索
            if not trends or len(trends) == 0:
                print("4. everythingエンドポイントで検索を試行...")
                trends = self._get_news_trends_everything(country, page_size)
            
            # 5. サンプルデータ（最後の手段）
            if not trends or len(trends) == 0:
                print("5. サンプルデータを生成...")
                trends = self._get_sample_news_data()
            
            return trends
            
        except Exception as e:
            print(f"News API エラー: {e}")
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
            
            print(f"カテゴリ付きリクエスト: {params}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"News API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            print(f"News API レスポンス: {data}")
            
            if data.get('status') != 'ok':
                print(f"News API レスポンスエラー: {data.get('message', 'Unknown error')}")
                return None
            
            articles = data.get('articles', [])
            print(f"カテゴリ '{category}' で取得記事数: {len(articles)}件")
            
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
            print(f"カテゴリ付きNews API エラー: {e}")
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
            
            print(f"カテゴリなしリクエスト: {params}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"News API エラー: HTTP {response.status_code}")
                return None
            
            data = response.json()
            print(f"News API レスポンス: {data}")
            
            if data.get('status') != 'ok':
                print(f"News API レスポンスエラー: {data.get('message', 'Unknown error')}")
                return None
            
            articles = data.get('articles', [])
            print(f"カテゴリなしで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                print("カテゴリなしでも記事が取得できませんでした")
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
            
            print(f"カテゴリなしで処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            print(f"カテゴリなしNews API エラー: {e}")
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
            
            print(f"everythingエンドポイントリクエスト: {params}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"News API everything エラー: HTTP {response.status_code}")
                return []
            
            data = response.json()
            print(f"News API everything レスポンス: {data}")
            
            if data.get('status') != 'ok':
                print(f"News API everything レスポンスエラー: {data.get('message', 'Unknown error')}")
                return []
            
            articles = data.get('articles', [])
            print(f"everythingエンドポイントで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                print("everythingエンドポイントでも記事が取得できませんでした")
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
            
            print(f"everythingエンドポイントで処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            print(f"everythingエンドポイントNews API エラー: {e}")
            return []
    
    def _get_sample_news_data(self):
        """サンプルのニュースデータを生成（テスト用）"""
        print("サンプルニュースデータを生成します")
        
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
        
        print(f"サンプルニュースデータ生成完了: {len(sample_news)}件")
        return sample_news
    
    def get_from_cache(self, country, category):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_news_trends_from_cache(country, category)
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, country, category):
        """データをキャッシュに保存"""
        try:
            self.db.save_news_trends_to_cache(data, country, category)
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def is_cache_valid(self, country, category):
        """キャッシュが有効かチェック"""
        try:
            return self.db.is_news_cache_valid(country, category)
        except Exception as e:
            print(f"キャッシュ有効性チェックエラー: {e}")
            return False 