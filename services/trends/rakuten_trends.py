import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database_config import TrendsCache

# 環境変数を明示的に読み込み
load_dotenv()

class RakutenTrendsManager:
    """楽天のトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.db = TrendsCache()
        self.rakuten_app_id = os.getenv('RAKUTEN_APP_ID')
        self.rakuten_affiliate_id = os.getenv('RAKUTEN_AFFILIATE_ID')
        
        print(f"Rakuten Trends Manager初期化:")
        print(f"  App ID: {'設定済み' if self.rakuten_app_id else '未設定'}")
        print(f"  Affiliate ID: {'設定済み' if self.rakuten_affiliate_id else '未設定'}")
        
        # デバッグ: 環境変数の値を確認
        print(f"  App ID値: {self.rakuten_app_id}")
        print(f"  Affiliate ID値: {self.rakuten_affiliate_id}")
    
    def get_trends(self, genre_id=None, limit=25, force_refresh=False):
        """楽天トレンドを取得（get_popular_itemsのエイリアス）"""
        return self.get_popular_items(genre_id, limit, force_refresh)
    
    def get_popular_items(self, genre_id=None, limit=25, force_refresh=False):
        """楽天人気商品を取得"""
        if not self.rakuten_app_id:
            return {'error': '楽天アプリケーションIDが設定されていません'}
        
        try:
            # キャッシュから取得を試行
            cached_data = self.get_from_cache(genre_id or 'all')
            if cached_data and not force_refresh:
                cache_info = self._get_cache_info(genre_id or 'all')
                return {
                    'data': cached_data,
                    'status': 'cached',
                    'genre_id': genre_id,
                    'cache_info': cache_info
                }
            
            # 1日1回のみAPIを呼び出し
            if not force_refresh and not self._should_refresh_cache(genre_id or 'all'):
                print(f"⚠️ 楽天のキャッシュは今日既に更新済みです。キャッシュデータを使用します。")
                if cached_data:
                    cache_info = self._get_cache_info(genre_id or 'all')
                    return {
                        'data': cached_data,
                        'status': 'cached',
                        'genre_id': genre_id,
                        'cache_info': cache_info
                    }
            
            # 楽天商品ランキングAPIを試す
            ranking_result = self._get_rakuten_ranking(genre_id, limit)
            if ranking_result and 'data' in ranking_result and ranking_result['data']:
                # キャッシュに保存
                self.save_to_cache(ranking_result['data'], genre_id or 'all')
                # 更新日時を記録
                self._update_refresh_time(genre_id or 'all')
                return ranking_result
            
            # ランキングAPIが失敗した場合は商品検索APIを使用
            search_result = self._get_rakuten_search(genre_id, limit)
            if search_result and 'data' in search_result and search_result['data']:
                # キャッシュに保存
                self.save_to_cache(search_result['data'], genre_id or 'all')
                # 更新日時を記録
                self._update_refresh_time(genre_id or 'all')
            return search_result
        
        except Exception as e:
            return {'error': f'楽天トレンド取得エラー: {str(e)}'}
    
    def _get_rakuten_ranking(self, genre_id=None, limit=25):
        """楽天商品ランキングAPIを使用"""
        try:
            url = "https://app.rakuten.co.jp/services/api/IchibaItem/Ranking/20170628"
            params = {
                'applicationId': self.rakuten_app_id,
                'format': 'json',
                'hits': limit,
                'sort': 'standard'  # 楽天の標準的な並び順
            }
            
            if self.rakuten_affiliate_id:
                params['affiliateId'] = self.rakuten_affiliate_id
            
            if genre_id:
                params['genreId'] = genre_id
            
            print(f"楽天ランキングAPIリクエストURL: {url}")
            print(f"楽天ランキングAPIリクエストパラメータ: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            print(f"楽天ランキングAPIレスポンスステータス: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('Items', [])
                
                # デバッグ: 最初のアイテムの全フィールドを確認
                if items:
                    first_item = items[0].get('Item', {})
                    print(f"楽天APIアイテムフィールド: {list(first_item.keys())}")
                    print(f"楽天APIアイテムサンプル: {first_item}")
                
                trends_data = []
                for item in items:
                    item_info = item.get('Item', {})
                    trends_data.append({
                        'rank': item_info.get('rank', len(trends_data) + 1),
                        'title': item_info.get('itemName', ''),
                        'price': item_info.get('itemPrice', 0),
                        'review_count': item_info.get('reviewCount', 0),
                        'review_average': item_info.get('reviewAverage', 0),
                        'image_url': item_info.get('mediumImageUrls', [{}])[0].get('imageUrl', ''),
                        'url': item_info.get('itemUrl', ''),
                        'shop_name': item_info.get('shopName', ''),
                        'genre_id': item_info.get('genreId', ''),
                        'sales_rank': item_info.get('salesRank', 'N/A'),  # 売上ランク
                        'sales_count': item_info.get('salesCount', 'N/A')  # 売上数
                    })
                
                # レビュー数でソート（降順）
                trends_data.sort(key=lambda x: x['review_count'], reverse=True)
                
                # ランクを再設定
                for i, item in enumerate(trends_data):
                    item['rank'] = i + 1
                
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': '楽天商品ランキングAPI',
                    'total_count': len(trends_data)
                }
            else:
                print(f"楽天ランキングAPIエラー: {response.text}")
                return None
                
        except Exception as e:
            print(f"楽天ランキングAPIエラー: {str(e)}")
            return None
    
    def _get_rakuten_search(self, genre_id=None, limit=25):
        """楽天商品検索APIを使用"""
        try:
            # 楽天商品検索API (最新バージョン)
            url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
            params = {
                'applicationId': self.rakuten_app_id,
                'format': 'json',
                'sort': '+sales',  # 売上順（より人気の商品）
                'hits': limit,
                'availability': 1,  # 在庫あり
                'field': 1  # 商品情報を詳細に
            }
            
            # アフィリエイトIDが設定されている場合のみ追加
            if self.rakuten_affiliate_id:
                params['affiliateId'] = self.rakuten_affiliate_id
            
            if genre_id:
                params['genreId'] = genre_id
            else:
                # デフォルトで人気のキーワード検索（より一般的な商品を取得）
                params['keyword'] = '人気'
            
            print(f"楽天APIリクエストURL: {url}")
            print(f"楽天APIリクエストパラメータ: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            print(f"楽天APIレスポンスステータス: {response.status_code}")
            print(f"楽天APIレスポンス内容: {response.text[:500]}...")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('Items', [])
                
                # データを整形
                trends_data = []
                for item in items:
                    item_info = item.get('Item', {})
                    trends_data.append({
                        'rank': len(trends_data) + 1,
                        'title': item_info.get('itemName', ''),
                        'price': item_info.get('itemPrice', 0),
                        'review_count': item_info.get('reviewCount', 0),
                        'review_average': item_info.get('reviewAverage', 0),
                        'image_url': item_info.get('mediumImageUrls', [{}])[0].get('imageUrl', ''),
                        'url': item_info.get('itemUrl', ''),
                        'shop_name': item_info.get('shopName', ''),
                        'genre_id': item_info.get('genreId', ''),
                        'sales_rank': item_info.get('salesRank', 'N/A'),  # 売上ランク
                        'sales_count': item_info.get('salesCount', 'N/A')  # 売上数
                    })
                
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': '楽天商品検索API',
                    'total_count': data.get('count', 0)
                }
            else:
                print(f"楽天APIエラーレスポンス: {response.text}")
                return {'error': f'楽天API エラー: {response.status_code} - {response.text}'}
                
        except Exception as e:
            return {'error': f'楽天トレンド取得エラー: {str(e)}'}
    
    def get_genres(self):
        """楽天ジャンル一覧を取得"""
        if not self.rakuten_app_id:
            return {'error': '楽天アプリケーションIDが設定されていません'}
        
        try:
            url = "https://app.rakuten.co.jp/services/api/IchibaGenre/Search/20140222"
            params = {
                'applicationId': self.rakuten_app_id,
                'format': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'data': data.get('children', []),
                    'status': 'success',
                    'source': '楽天ジャンル検索API'
                }
            else:
                return {'error': f'楽天ジャンルAPI エラー: {response.status_code}'}
                
        except Exception as e:
            return {'error': f'楽天ジャンル取得エラー: {str(e)}'}
    
    def get_rakuten_trends_summary(self):
        """楽天トレンドの概要を取得"""
        return {
            'rakuten_api': {
                'available': bool(self.rakuten_app_id),
                'note': '楽天商品検索API: 人気商品、レビュー数順',
                'features': [
                    '商品検索・ランキング',
                    'ジャンル別分類',
                    'レビュー数・評価',
                    '価格情報',
                    'アフィリエイトリンク生成'
                ]
            },
            'limitations': [
                '公式トレンドAPIなし',
                'レビュー数順での人気商品取得',
                'リアルタイムトレンドではない'
            ],
            'setup_required': [
                '楽天デベロッパーID取得',
                'アフィリエイトID取得（オプション）'
            ]
        }
    
    def _should_refresh_cache(self, genre_id):
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
                    """, ('rakuten_trends',))
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        last_refresh = result[0].date()
                        return last_refresh < today
                    return True  # 初回は更新する
        except Exception as e:
            print(f"キャッシュ更新日時チェックエラー: {e}")
            return True
    
    def get_from_cache(self, genre_id):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_rakuten_trends_cache(genre_id)
        except Exception as e:
            print(f"キャッシュ取得エラー: {e}")
            return None
    
    def save_to_cache(self, data, genre_id):
        """データをキャッシュに保存"""
        try:
            self.db.save_rakuten_trends_to_cache(data, genre_id)
        except Exception as e:
            print(f"キャッシュ保存エラー: {e}")
    
    def _update_refresh_time(self, genre_id):
        """キャッシュ更新日時を記録"""
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
                        ON CONFLICT (cache_key) 
                        DO UPDATE SET 
                            last_updated = EXCLUDED.last_updated,
                            data_count = EXCLUDED.data_count
                    """, ('rakuten_trends', now, 30))  # 正しいキャッシュキーを使用
                    conn.commit()
        except Exception as e:
            print(f"更新日時記録エラー: {e}")
    
    def _get_cache_info(self, genre_id):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE country_code = %s
                    """, (f'rakuten',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'last_updated': result[0].isoformat() if result[0] else None,
                            'data_count': result[1] or 0
                        }
                    return {'last_updated': None, 'data_count': 0}
        except Exception as e:
            print(f"キャッシュ情報取得エラー: {e}")
            return {'last_updated': None, 'data_count': 0}
