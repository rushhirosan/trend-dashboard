import os
import gc
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.dummy_data_generator import generate_dummy_rakuten_data
from utils.rate_limiter import get_rakuten_api_rate_limiter
from services.trends.base_trends_manager import BaseTrendsManager

# 環境変数を明示的に読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

# はてなカテゴリに合わせた楽天ジャンル対応（本は本トレンドで取得済みのため除外）
# キー: カテゴリID（UI用）、値: 楽天ジャンルID（'all' または数値文字列）
RAKUTEN_CATEGORY_GENRE_MAP = {
    'all': 'all',           # 全ジャンル
    'it': '565162',         # パソコン
    'social': '100554',     # 生活雑貨
    'entertainment': '101205',  # テレビゲーム
    'life': '555086',       # レディーストップス（暮らし・ファッション）
    'knowledge': '100901',  # 文房具・事務用品
}

# カテゴリ表示名（はてなに合わせたラベル）
RAKUTEN_CATEGORY_LABELS = {
    'all': '総合',
    'it': 'テクノロジー',
    'social': 'ニュース・社会',
    'entertainment': 'エンタメ',
    'life': '暮らし',
    'knowledge': '学び',
}

# 2026-05 移行後の楽天市場API（旧 app.rakuten.co.jp / 20170628 は廃止）
RAKUTEN_RANKING_URL = (
    'https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601'
)
RAKUTEN_SEARCH_URL = (
    'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601'
)
RAKUTEN_GENRE_URL = (
    'https://openapi.rakuten.co.jp/ichibagt/api/IchibaGenre/Search/20170711'
)


class RakutenTrendsManager(BaseTrendsManager):
    """楽天のトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='rakuten', max_requests=10, window_seconds=60)
        # 楽天API制限「1秒1回」に準拠するため共有レート制限を使用
        self.rate_limiter = get_rakuten_api_rate_limiter()
        
        self.rakuten_app_id = os.getenv('RAKUTEN_APP_ID')
        self.rakuten_access_key = (os.getenv('RAKUTEN_ACCESS_KEY') or '').strip()
        self.rakuten_affiliate_id = (os.getenv('RAKUTEN_AFFILIATE_ID') or '').strip()
        
        logger.info(f"Rakuten Trends Manager初期化:")
        logger.info(f"  App ID: {'設定済み' if self.rakuten_app_id else '未設定'}")
        logger.info(f"  Access Key: {'設定済み' if self.rakuten_access_key else '未設定'}")
        if self.rakuten_affiliate_id:
            logger.info(f"  Affiliate ID: 設定済み")
        else:
            logger.warning(f"  Affiliate ID: 未設定（.env の RAKUTEN_AFFILIATE_ID を設定するとアフィリエイトリンクが有効になります）")
    
    def _rakuten_credentials_ok(self) -> bool:
        return bool(self.rakuten_app_id and self.rakuten_access_key)

    def _rakuten_auth_params(self) -> dict:
        params = {
            'applicationId': self.rakuten_app_id,
            'accessKey': self.rakuten_access_key,
            'format': 'json',
        }
        if self.rakuten_affiliate_id:
            params['affiliateId'] = self.rakuten_affiliate_id
        return params

    def _rakuten_credentials_error(self) -> str:
        missing = []
        if not self.rakuten_app_id:
            missing.append('RAKUTEN_APP_ID')
        if not self.rakuten_access_key:
            missing.append('RAKUTEN_ACCESS_KEY')
        return f"{' と '.join(missing)} が未設定です（楽天API移行後は両方必須）"

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

    def get_trends(self, genre_id=None, limit=25, force_refresh=False, fetch_all_categories=False):
        """楽天トレンドを取得（ベースクラスの共通処理を使用）"""
        # 全カテゴリを取得する場合（スケジューラー用、はてな同様）
        if fetch_all_categories:
            logger.info("🔄 楽天商品: 全カテゴリのデータを取得します")
            rows_all, last_error, any_saved = self._fetch_and_cache_all_categories(limit)
            if any_saved:
                return {
                    'data': rows_all[:limit] if rows_all else [],
                    'status': 'api_fetched',
                    'genre_id': 'all',
                    'source': '楽天商品ランキングAPI',
                    'success': True
                }
            stale = self._get_from_cache(genre_id='all')
            if stale and len(stale) > 0:
                self._normalize_sales_count(stale)
                logger.info(
                    "✅ 楽天商品: API失敗のため既存キャッシュを返します (%d件)",
                    len(stale),
                )
                return {
                    'data': stale[:limit],
                    'status': 'stale_cache_preserved',
                    'genre_id': 'all',
                    'source': 'database_cache',
                    'success': True,
                    'message': '楽天API取得に失敗したため、保存済みのキャッシュを表示しています。',
                    'error': last_error,
                }
            error_msg = last_error or '全カテゴリのデータ取得に失敗しました'
            return {
                'data': [],
                'status': 'api_error',
                'genre_id': 'all',
                'error': error_msg,
                'success': False
            }

        cache_scope = genre_id or 'all'
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュ未ヒット時はAPI呼び出し（レート制限1秒1回で制御）
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

    def get_available_categories(self):
        """利用可能なカテゴリ一覧を取得（はてなに合わせた5+総合）"""
        return [
            {'id': k, 'name': RAKUTEN_CATEGORY_LABELS[k], 'genre_id': v}
            for k, v in RAKUTEN_CATEGORY_GENRE_MAP.items()
        ]

    def _fetch_and_cache_all_categories(self, limit=25):
        """全カテゴリを順に取得し、ジャンルごとにキャッシュへ保存（ピークメモリ抑制）

        Returns:
            tuple: (rows_for_all_genre: list, last_error: str|None, any_saved: bool)
        """
        if not self._rakuten_credentials_ok():
            logger.warning("楽天ランキングAPI: %s", self._rakuten_credentials_error())
            return [], self._rakuten_credentials_error(), False
        rows_for_all_genre = []
        last_error = None
        any_saved = False
        try:
            logger.info("🔄 楽天商品: 全カテゴリのデータを取得開始")
            categories = self.get_available_categories()

            for cat in categories:
                genre_id = cat.get('genre_id', 'all')
                cat_id = cat.get('id', genre_id)
                logger.info(f"📊 楽天ジャンル '{genre_id}' ({RAKUTEN_CATEGORY_LABELS.get(cat_id, cat_id)}) のデータを取得中...")
                result = self._get_rakuten_ranking(genre_id, limit)
                if result and result.get('data'):
                    for item in result['data']:
                        item['genre_id'] = genre_id
                    data = result['data']
                    if self.db.save_rakuten_trends_to_cache(data, genre_id):
                        any_saved = True
                        logger.info(f"✅ ジャンル '{genre_id}': {len(data)}件取得・キャッシュ保存")
                    if genre_id == 'all':
                        rows_for_all_genre = list(data)
                else:
                    err = (result.get('error') if isinstance(result, dict) else None) or str(result)
                    last_error = err
                    logger.warning(f"❌ ジャンル '{genre_id}': データ取得失敗 - {err}")
                gc.collect()

            if any_saved:
                logger.info("✅ 楽天商品: 全カテゴリのデータ取得・保存完了")
            else:
                logger.warning(f"❌ 楽天商品: 取得したデータがありません (最終エラー: {last_error})")
            return rows_for_all_genre, last_error, any_saved
        except Exception as e:
            err_msg = str(e)
            logger.error(f"❌ 楽天商品: 全カテゴリ取得エラー: {e}", exc_info=True)
            return [], err_msg, False

    def _save_all_categories_to_cache(self, all_data):
        """全カテゴリのデータをキャッシュに保存"""
        if not all_data:
            return 0
        try:
            saved_count = 0
            for genre_id in RAKUTEN_CATEGORY_GENRE_MAP.values():
                genre_data = [item for item in all_data if item.get('genre_id') == genre_id]
                if genre_data:
                    success = self.db.save_rakuten_trends_to_cache(genre_data, genre_id)
                    if success:
                        saved_count += len(genre_data)
                        logger.info(f"✅ 楽天ジャンル '{genre_id}': {len(genre_data)}件をキャッシュに保存しました")
            if saved_count > 0:
                logger.info(f"✅ 楽天商品: 全カテゴリのデータをキャッシュに保存完了 ({saved_count}件)")
            return saved_count
        except Exception as e:
            logger.error(f"❌ 楽天商品: 全カテゴリキャッシュ保存エラー: {e}", exc_info=True)
            return 0

    def _parse_rakuten_ranking_items(self, items, limit=25):
        """ランキングAPIレスポンスを共通形式に変換"""
        trends_data = []
        for item in items:
            item_info = (
                item.get('Item') or item.get('item') or item
                if isinstance(item, dict) else {}
            )
            rank = item_info.get('rank')
            if rank is None:
                rank = len(trends_data) + 1
            sales_count = item_info.get('salesCount', 0)
            if isinstance(sales_count, str) and sales_count != 'N/A':
                try:
                    sales_count = int(sales_count)
                except Exception:
                    sales_count = 0
            elif sales_count == 'N/A' or sales_count is None:
                sales_count = 0

            image_urls = item_info.get('mediumImageUrls') or item_info.get('smallImageUrls') or []
            image_url = ''
            if image_urls and isinstance(image_urls[0], dict):
                image_url = image_urls[0].get('imageUrl', '')

            trends_data.append({
                'item_id': item_info.get('itemCode', ''),
                'title': item_info.get('itemName', ''),
                'price': item_info.get('itemPrice', 0),
                'review_count': item_info.get('reviewCount', 0),
                'review_average': item_info.get('reviewAverage', 0),
                'image_url': image_url,
                'url': self._add_affiliate_params(
                    item_info.get('itemUrl') or item_info.get('affiliateUrl', '')
                ),
                'shop_name': item_info.get('shopName', ''),
                'genre_id': item_info.get('genreId', ''),
                'sales_rank': rank,
                'sales_count': sales_count,
                'rank': rank,
            })
            if len(trends_data) >= limit:
                break
        return trends_data

    def _get_rakuten_ranking(self, genre_id=None, limit=25, _retry_count=0):
        """楽天商品ランキングAPIを使用（429/503時はリトライ）"""
        max_retries = 2
        retry_delay = 30  # 秒（楽天APIのレート制限緩和待ち）

        if not self._rakuten_credentials_ok():
            logger.warning("楽天ランキングAPI: %s", self._rakuten_credentials_error())
            return {'data': [], 'error': self._rakuten_credentials_error()}
        try:
            params = {
                **self._rakuten_auth_params(),
                'formatVersion': 2,
                'page': 1,
            }

            # 楽天APIのgenreIdは数値形式のみ。'all'や空は渡さない（全ジャンルランキングになる）
            if genre_id and str(genre_id).strip() != 'all' and str(genre_id).isdigit():
                params['genreId'] = str(genre_id).strip()

            logger.debug(f"楽天ランキングAPIリクエストURL: {RAKUTEN_RANKING_URL}")
            logger.debug(f"楽天ランキングAPIリクエストパラメータ: {params}")

            # レート制限をチェック
            self.rate_limiter.wait_if_needed()

            response = requests.get(RAKUTEN_RANKING_URL, params=params, timeout=15)
            logger.debug(f"楽天ランキングAPIレスポンスステータス: {response.status_code}")

            # 429(レート制限) / 503(メンテ) の場合はリトライ
            if response.status_code in (429, 503) and _retry_count < max_retries:
                try:
                    err_body = response.json()
                    err_desc = err_body.get('error_description', err_body.get('error', ''))
                except Exception:
                    err_desc = response.text[:200] if response.text else ''
                logger.warning(
                    f"楽天API {response.status_code} (試行{_retry_count + 1}/{max_retries + 1}): "
                    f"{err_desc} - {retry_delay}秒後にリトライします"
                )
                time.sleep(retry_delay)
                return self._get_rakuten_ranking(genre_id, limit, _retry_count=_retry_count + 1)

            if response.status_code == 200:
                data = response.json()
                # 200でもerrorが含まれる場合がある（一部エラーケース）
                if isinstance(data, dict) and data.get('error'):
                    err_desc = data.get('error_description', data.get('error', ''))
                    return {'data': [], 'error': f'楽天API エラー: {err_desc}'}
                items = data.get('Items') or data.get('items', [])
                trends_data = self._parse_rakuten_ranking_items(items, limit=limit)
                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': '楽天商品ランキングAPI',
                    'total_count': len(trends_data)
                }

            err_text = (response.text or '')[:500]
            logger.error(f"楽天ランキングAPIエラー: {err_text}")
            # ランキングAPI失敗時は検索APIへフォールバック
            if response.status_code in (400, 404, 503):
                logger.info("楽天ランキングAPI失敗のため検索APIへフォールバックします (genre_id=%s)", genre_id)
                return self._get_rakuten_search(genre_id, limit)
            return {'data': [], 'error': f'楽天API HTTP {response.status_code}: {err_text}'}

        except Exception as e:
            logger.error(f"楽天ランキングAPIエラー: {str(e)}", exc_info=True)
            return {'data': [], 'error': f'楽天API 例外: {str(e)}'}
    
    def _get_rakuten_search(self, genre_id=None, limit=25):
        """楽天商品検索APIを使用（ランキングAPI失敗時のフォールバック）"""
        if not self._rakuten_credentials_ok():
            return {'data': [], 'error': self._rakuten_credentials_error()}
        try:
            params = {
                **self._rakuten_auth_params(),
                'sort': '+sales',
                'hits': limit,
                'availability': 1,
                'formatVersion': 2,
            }

            # genreIdは数値形式のみ。'all'や空は渡さず、keywordで検索
            if genre_id and str(genre_id).strip() != 'all' and str(genre_id).isdigit():
                params['genreId'] = str(genre_id).strip()
            else:
                params['keyword'] = '人気'

            logger.debug(f"楽天検索APIリクエストURL: {RAKUTEN_SEARCH_URL}")
            logger.debug(f"楽天検索APIリクエストパラメータ: {params}")

            self.rate_limiter.wait_if_needed()

            response = requests.get(RAKUTEN_SEARCH_URL, params=params, timeout=10)
            logger.debug(f"楽天検索APIレスポンスステータス: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and data.get('error'):
                    err_desc = data.get('error_description', data.get('error', ''))
                    return {'data': [], 'error': f'楽天API エラー: {err_desc}'}
                items = data.get('Items') or data.get('items', [])

                trends_data = []
                for item in items:
                    item_info = (
                        item.get('Item') or item.get('item') or item
                        if isinstance(item, dict) else {}
                    )
                    image_urls = item_info.get('mediumImageUrls') or item_info.get('smallImageUrls') or []
                    image_url = ''
                    if image_urls and isinstance(image_urls[0], dict):
                        image_url = image_urls[0].get('imageUrl', '')
                    rank = len(trends_data) + 1
                    trends_data.append({
                        'rank': rank,
                        'item_id': item_info.get('itemCode', ''),
                        'title': item_info.get('itemName', ''),
                        'price': item_info.get('itemPrice', 0),
                        'review_count': item_info.get('reviewCount', 0),
                        'review_average': item_info.get('reviewAverage', 0),
                        'image_url': image_url,
                        'url': self._add_affiliate_params(item_info.get('itemUrl', '')),
                        'shop_name': item_info.get('shopName', ''),
                        'genre_id': item_info.get('genreId', ''),
                        'sales_rank': item_info.get('salesRank', rank),
                        'sales_count': item_info.get('salesCount', 0),
                    })
                    if len(trends_data) >= limit:
                        break

                return {
                    'data': trends_data,
                    'status': 'success',
                    'source': '楽天商品検索API',
                    'total_count': data.get('count', len(trends_data))
                }
            else:
                logger.error(f"楽天検索APIエラーレスポンス: {response.text}")
                return {'data': [], 'error': f'楽天API エラー: {response.status_code} - {response.text[:500]}'}

        except Exception as e:
            return {'data': [], 'error': f'楽天トレンド取得エラー: {str(e)}'}
    
    def get_genres(self):
        """楽天ジャンル一覧を取得"""
        if not self._rakuten_credentials_ok():
            return {'error': self._rakuten_credentials_error()}

        try:
            params = self._rakuten_auth_params()

            self.rate_limiter.wait_if_needed()

            response = requests.get(RAKUTEN_GENRE_URL, params=params, timeout=10)
            
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
