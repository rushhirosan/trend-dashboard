import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.dummy_data_generator import generate_dummy_rakuten_data
from services.trends.base_trends_manager import BaseTrendsManager

# 環境変数を明示的に読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

class RakutenTrendsManager(BaseTrendsManager):
    """楽天のトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='rakuten', max_requests=10, window_seconds=60)
        
        self.rakuten_app_id = os.getenv('RAKUTEN_APP_ID')
        self.rakuten_affiliate_id = os.getenv('RAKUTEN_AFFILIATE_ID')
        
        logger.info(f"Rakuten Trends Manager初期化:")
        logger.info(f"  App ID: {'設定済み' if self.rakuten_app_id else '未設定'}")
        logger.info(f"  Affiliate ID: {'設定済み' if self.rakuten_affiliate_id else '未設定'}")
    
    def _add_affiliate_params(self, url: str) -> str:
        """楽天アイテムURLにaffiliateIdを付与（既に付与済みなら何もしない）"""
        if not url or not self.rakuten_affiliate_id:
            return url
        try:
            from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
            parsed = urlparse(url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if query.get('affiliateId'):
                return url
            query['affiliateId'] = self.rakuten_affiliate_id
            new_query = urlencode(query, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            return url
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        genre_id = kwargs.get('genre_id', None)
        cache_scope = genre_id or 'all'
        return f'rakuten_trends_{cache_scope}'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            genre_id = kwargs.get('genre_id', None)
            cache_scope = genre_id or 'all'
            data = self.db.get_rakuten_trends_from_cache(cache_scope)
            if data:
                self._normalize_sales_count(data)
            return data
        except Exception as e:
            logger.error(f"❌ Rakuten: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            genre_id = kwargs.get('genre_id', None)
            cache_scope = genre_id or 'all'
            return self.db.save_rakuten_trends_to_cache(data, cache_scope)
        except Exception as e:
            logger.error(f"❌ Rakuten キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            genre_id = kwargs.get('genre_id', None)
            cache_scope = genre_id or 'all'
            return self.db.clear_rakuten_trends_cache(cache_scope)
        except Exception as e:
            logger.error(f"❌ Rakuten キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Rakuten: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, genre_id=None, limit=25, *args, **kwargs):
        """外部APIから楽天データを取得"""
        result = self._get_rakuten_ranking(genre_id, limit)
        if result and result.get('data'):
            return {
                'success': True,
                'data': result['data'],
                'status': 'api_fetched',
                'genre_id': genre_id,
                'source': '楽天商品ランキングAPI'
            }
        # 失敗時: _get_rakuten_ranking が返した error を使い、Discord/ログで原因が分かるようにする
        error_msg = (result.get('error') if isinstance(result, dict) else None) or 'データが取得できませんでした'
        return {
            'success': False,
            'error': error_msg,
            'data': []
        }

    def _generate_dummy_data(self, limit=25, *args, **kwargs):
        """楽天用ダミーデータを生成（USE_DUMMY_DATA 時）"""
        genre_id = kwargs.get('genre_id')
        cache_scope = genre_id or 'all'
        return generate_dummy_rakuten_data(limit=limit, genre_id=cache_scope)

    def _normalize_sales_count(self, data):
        """sales_countを数値に正規化（ソート・表示用）"""
        if not data:
            return
        for item in data:
            sc = item.get('sales_count', 'N/A')
            if isinstance(sc, str) and sc != 'N/A':
                try:
                    item['sales_count'] = int(sc)
                except Exception:
                    item['sales_count'] = 0
            elif sc == 'N/A' or sc is None:
                item['sales_count'] = 0

    def get_trends(self, genre_id=None, limit=25, force_refresh=False):
        """楽天トレンドを取得（ベースクラスの共通処理を使用）"""
        cache_scope = genre_id or 'all'
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 楽天はキャッシュ未ヒット時はAPI呼び出さない（force_refresh時のみ）
            sort_key='sales_count',
            sort_reverse=True,
            genre_id=cache_scope
        )
        if result and isinstance(result, dict):
            result['genre_id'] = genre_id
        return result

    def get_popular_items(self, genre_id=None, limit=25, force_refresh=False):
        """楽天人気商品を取得（get_trendsのエイリアス）"""
        return self.get_trends(genre_id=genre_id, limit=limit, force_refresh=force_refresh)
    
    def _get_rakuten_ranking(self, genre_id=None, limit=25):
        """楽天商品ランキングAPIを使用"""
        if not self.rakuten_app_id:
            logger.warning("楽天ランキングAPI: RAKUTEN_APP_ID が未設定です")
            return {'data': [], 'error': 'RAKUTEN_APP_ID が未設定です'}
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
            
            logger.debug(f"楽天ランキングAPIリクエストURL: {url}")
            logger.debug(f"楽天ランキングAPIリクエストパラメータ: {params}")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            logger.debug(f"楽天ランキングAPIレスポンスステータス: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('Items', [])
                
                trends_data = []
                for item in items:
                    item_info = item.get('Item', {})
                    # sales_countを数値に変換（'N/A'の場合は0）
                    sales_count = item_info.get('salesCount', 'N/A')
                    if isinstance(sales_count, str) and sales_count != 'N/A':
                        try:
                            sales_count = int(sales_count)
                        except:
                            sales_count = 0
                    elif sales_count == 'N/A' or sales_count is None:
                        sales_count = 0
                    
                    trends_data.append({
                        'item_id': item_info.get('itemCode', ''),  # itemCodeをitem_idとして追加
                        'title': item_info.get('itemName', ''),
                        'price': item_info.get('itemPrice', 0),
                        'review_count': item_info.get('reviewCount', 0),
                        'review_average': item_info.get('reviewAverage', 0),
                        'image_url': item_info.get('mediumImageUrls', [{}])[0].get('imageUrl', ''),
                        'url': self._add_affiliate_params(item_info.get('itemUrl', '')),
                        'shop_name': item_info.get('shopName', ''),
                        'genre_id': item_info.get('genreId', ''),
                        'sales_rank': item_info.get('salesRank', 'N/A'),  # 売上ランク
                        'sales_count': sales_count  # 売上数（数値に変換済み）
                    })
                
                # 売上数でソート（降順）、同じ場合はレビュー数でソート
                trends_data.sort(key=lambda x: (x.get('sales_count', 0), x.get('review_count', 0)), reverse=True)
                
                # ランクを再設定
                for i, item in enumerate(trends_data, 1):
                    item['rank'] = i
                
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': '楽天商品ランキングAPI',
                    'total_count': len(trends_data)
                }
            else:
                err_text = (response.text or '')[:500]
                logger.error(f"楽天ランキングAPIエラー: {err_text}")
                return {'data': [], 'error': f'楽天API HTTP {response.status_code}: {err_text}'}
                
        except Exception as e:
            logger.error(f"楽天ランキングAPIエラー: {str(e)}", exc_info=True)
            return {'data': [], 'error': f'楽天API 例外: {str(e)}'}
    
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
            
            logger.debug(f"楽天APIリクエストURL: {url}")
            logger.debug(f"楽天APIリクエストパラメータ: {params}")
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(url, params=params, timeout=10)
            logger.debug(f"楽天APIレスポンスステータス: {response.status_code}")
            logger.debug(f"楽天APIレスポンス内容: {response.text[:500]}...")
            
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
                        'url': self._add_affiliate_params(item_info.get('itemUrl', '')),
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
                logger.error(f"楽天APIエラーレスポンス: {response.text}")
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
            
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
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
                logger.info(f"⚠️ 時間外です（{current_hour}時）。キャッシュデータを使用します。")
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
            logger.error(f"キャッシュ更新日時チェックエラー: {e}", exc_info=True)
            return True
    
    def get_from_cache(self, genre_id):
        """キャッシュからデータを取得"""
        try:
            return self.db.get_rakuten_trends_from_cache(genre_id)
        except Exception as e:
            logger.error(f"キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def save_to_cache(self, data, genre_id):
        """データをキャッシュに保存"""
        try:
            self.db.save_rakuten_trends_to_cache(data, genre_id)
            # cache_statusテーブルも更新
            self._update_refresh_time(genre_id or 'all')
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}", exc_info=True)
    
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
            logger.error(f"更新日時記録エラー: {e}", exc_info=True)
    
    def _get_cache_info(self, genre_id):
        """キャッシュ情報を取得"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT last_updated, data_count 
                        FROM cache_status 
                        WHERE cache_key = %s
                    """, ('rakuten_trends',))
                    
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
