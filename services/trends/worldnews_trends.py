import os
import requests
from datetime import datetime, timedelta
from database_config import TrendsCache

class WorldNewsTrendsManager:
    """World News APIを使用して日本のニューストレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.api_key = os.getenv('WORLDNEWS_API_KEY')
        self.base_url = "https://api.worldnewsapi.com"
        self.db = TrendsCache()
        
        if not self.api_key:
            print("Warning: WORLDNEWS_API_KEYが設定されていません")
        
        print(f"World News API認証情報確認:")
        print(f"  API Key: {self.api_key[:10]}..." if self.api_key else "  API Key: 未設定")
        
        # World News API接続テスト（キャッシュモードでは無効化）
        # if self.api_key:
        #     self._test_connection()
    
    def _test_connection(self):
        """World News API接続テスト"""
        try:
            # 簡単なテストリクエスト（日本のニュース）
            test_url = f"{self.base_url}/search-news"
            params = {
                'api-key': self.api_key,
                'source-country': 'jp',
                'number': 1
            }
            
            response = requests.get(test_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"World News API接続テスト成功: {data.get('available', 0)}件の記事")
                print(f"レスポンス詳細: {data}")
            else:
                print(f"World News API接続テスト失敗: {response.status_code}")
                print(f"エラーレスポンス: {response.text}")
                
        except Exception as e:
            print(f"World News API接続テストエラー: {e}")
    
    def get_trends(self, country='jp', category=None, page_size=25, force_refresh=False):
        """日本のニューストレンドを取得"""
        try:
            cache_key = f"worldnews_{country}_{category or 'all'}"
            
            # force_refreshが指定された場合、キャッシュをクリア
            if force_refresh:
                print(f"🔄 World News force_refresh: キャッシュをクリアします")
                self.db.clear_news_trends_cache(country, category or 'general')
            
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache(category, country):
                print(f"⚠️ World Newsのキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                cached_data = self.get_from_cache(cache_key, country)
                if cached_data:
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'country': country.upper(),
                        'category': category,
                        'source': 'World News API'
                    }
            
            # キャッシュチェック
            if not force_refresh and self.is_cache_valid(cache_key, country):
                cached_data = self.get_from_cache(cache_key, country)
                if cached_data:
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'country': country.upper(),
                        'category': category,
                        'source': 'World News API'
                    }
            
            # 新しいデータを取得
            trends_data = self._get_worldnews_trends(country, category, page_size)
            
            if trends_data:
                # キャッシュに保存
                self.save_to_cache(trends_data, cache_key, country)
                return {
                    'data': trends_data,
                    'status': 'fresh',
                    'country': country.upper(),
                    'category': category,
                    'source': 'World News API'
                }
            else:
                return {'error': 'World News APIからデータを取得できませんでした。API認証情報を確認してください。'}
                
        except Exception as e:
            print(f"World News APIトレンド取得エラー: {e}")
            return {'error': f'World News APIトレンドの取得に失敗しました: {str(e)}'}
    
    def _get_worldnews_trends(self, country='jp', category=None, page_size=25):
        """World News APIからトレンドデータを取得"""
        if not self.api_key:
            print("World News APIキーが設定されていません")
            return None
        
        try:
            print(f"World News API呼び出し開始 (国: {country}, カテゴリ: {category})")
            
            url = f"{self.base_url}/search-news"
            params = {
                'api-key': self.api_key,
                'source-country': country,
                'number': page_size,
                'language': 'ja' if country == 'jp' else 'en'
            }
            
            # カテゴリが指定されている場合のみtextパラメータを追加
            # ただし、'general'の場合は除外（検索結果が0件になるため）
            if category and category != 'general':
                params['text'] = category
            
            print(f"World News APIリクエスト: {params}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"World News API エラー: HTTP {response.status_code}")
                print(f"エラーレスポンス: {response.text}")
                return None
            
            data = response.json()
            print(f"World News API レスポンス: {data}")
            
            articles = data.get('news', [])
            print(f"World News APIで取得記事数: {len(articles)}件")
            
            if len(articles) == 0:
                print("World News APIで記事が取得できませんでした")
                return []
            
            trends = []
            for i, article in enumerate(articles, 1):
                # スコア計算（順位ベース）
                score = 100 * (1 - (i - 1) / (len(articles) - 1)) if len(articles) > 1 else 100
                
                trends.append({
                    'rank': i,
                    'title': article.get('title', 'No Title'),
                    'description': article.get('text', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'url': article.get('url', ''),
                    'image_url': article.get('image', ''),
                    'published_at': article.get('publish_date', ''),
                    'score': round(score, 1),
                    'category': category or 'general'
                })
            
            print(f"World News API処理完了: {len(trends)}件のニューストレンドデータ")
            return trends
            
        except Exception as e:
            print(f"World News API エラー: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_from_cache(self, cache_key, country):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_news_trends_from_cache(country, cache_key)
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, cache_key, country):
        """データをキャッシュに保存"""
        try:
            self.db.save_worldnews_trends_to_cache(data, cache_key, country)
            # cache_statusテーブルも更新
            self._update_cache_status('worldnews_trends', len(data))
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            from datetime import datetime
            import pytz
            # 日本時間で現在時刻を取得
            jst = pytz.timezone('Asia/Tokyo')
            now = datetime.now(jst)
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO cache_status (cache_key, last_updated, data_count)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, (cache_key, now, data_count))
                    conn.commit()
        except Exception as e:
            print(f"cache_status更新エラー: {e}")
    
    def is_cache_valid(self, cache_key, country):
        """キャッシュが有効かチェック（6時間以内）"""
        try:
            return self.db.is_news_cache_valid(country, cache_key)
        except Exception as e:
            print(f"キャッシュ有効性チェックエラー: {e}")
            return False
    
    def _should_refresh_cache(self, category, country):
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
                print(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
                return False
            
            # データベースから最後の更新日時を取得
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('worldnews_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            print(f"キャッシュ更新日時チェックエラー: {e}")
            return True 