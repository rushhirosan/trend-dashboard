"""
書籍トレンド関連の処理を管理するモジュール
楽天ブックスAPI（日本）とGoogle Books API（US）を使用して書籍トレンドを取得
"""

import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rakuten_api_rate_limiter
from utils.dummy_data_generator import generate_dummy_book_data
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

# 日本（楽天）: 5択カテゴリ → 楽天 booksGenreId のリスト
# 楽天ブックス実ジャンル: 001001=本・雑誌（総合）, 001002=文学・エッセイ, 001003=絵本・児童書,
# 001004=小説・エッセイ, 001005=パソコン・システム開発, 001006=ビジネス・経済・就職,
# 001007=旅行・留学・アウトドア, 001008=人文・思想・社会, 001009=ホビー・スポーツ・美術, 001010=美容・暮らし・健康・料理
# 総合: 001001 のみだとAPIが0件を返す場合があるため、サブジャンルをまとめて取得
RAKUTEN_BOOK_CATEGORY_GENRES = {
    'all': ['001001', '001002', '001003', '001004', '001005', '001006', '001007', '001008', '001009', '001010'],
    'fiction': ['001004'],           # 文芸（小説・エッセイ）
    'business': ['001006'],          # ビジネス・経済・就職
    'humanities': ['001008'],        # 人文・思想・社会
    'practical': ['001005', '001007', '001009', '001010'],  # 実用・IT（PC・旅行・ホビー・美容・暮らし）
}

# US（Google Books）: 5択カテゴリ → subject 検索クエリ
GOOGLE_BOOK_CATEGORY_QUERIES = {
    'all': ['subject:fiction', 'subject:nonfiction', 'subject:bestseller', 'subject:popular'],
    'fiction': ['subject:fiction'],
    'business': ['subject:business'],
    'biography': ['subject:biography', 'subject:history'],
    'science': ['subject:science', 'subject:computers'],
}

class BookTrendsManager(BaseTrendsManager):
    """書籍トレンドの管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='book', max_requests=10, window_seconds=60)
        
        # 楽天ブックスAPI設定（日本向け）
        # 書籍ジャンル一覧: https://webservice.rakuten.co.jp/api/booksgenreidsearch/
        # 001001: 本・雑誌（総合）
        self.rakuten_base_url = "https://app.rakuten.co.jp/services/api/BooksTotal/Search/20170404"
        self.rakuten_ranking_url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        self.rakuten_app_id = os.getenv('RAKUTEN_APP_ID')
        
        # Google Books API設定（US向け）
        self.google_books_base_url = "https://www.googleapis.com/books/v1"
        self.google_books_api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
        
        # AmazonアソシエイトID設定
        self.amazon_affiliate_id = os.getenv('AMAZON_AFFILIATE_ID', '').strip()
        # 楽天アフィリエイトID設定（楽天ブックス用）
        self.rakuten_affiliate_id = os.getenv('RAKUTEN_AFFILIATE_ID', '').strip()
        
        logger.info("Book Trends Manager初期化完了")
        logger.info(f"  楽天ブックス App ID: {'設定済み' if self.rakuten_app_id else '未設定'}")
        logger.info(f"  Google Books API Key: {'設定済み' if self.google_books_api_key else '未設定'}")
        logger.info(f"  Amazon Affiliate ID: {'設定済み' if self.amazon_affiliate_id else '未設定'}")
        logger.info(f"  Rakuten Affiliate ID: {'設定済み' if self.rakuten_affiliate_id else '未設定'}")
    
    def _get_cache_key(self, *args, **kwargs):
        """キャッシュキーを返す"""
        country = kwargs.get('country', 'JP')
        category = kwargs.get('category', 'all')
        return f'book_trends_{country}_{category}'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            country = kwargs.get('country', 'JP')
            category = kwargs.get('category', 'all')
            return self.db.get_book_trends_from_cache(country, category)
        except Exception as e:
            logger.error(f"❌ Book: キャッシュ取得エラー: {e}", exc_info=True)
            return None

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            country = kwargs.get('country', 'JP')
            category = kwargs.get('category', 'all')
            return self.db.save_book_trends_to_cache(data, country, category)
        except Exception as e:
            logger.error(f"❌ Book キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア（cache_statusも同時にクリア）"""
        try:
            country = kwargs.get('country', 'JP')
            category = kwargs.get('category', 'all')
            cache_key = f'book_trends_{country}_{category}'
            cache_cleared = self.db.clear_book_trends_cache(country, category)
            try:
                self.db.update_cache_status(cache_key, 0)
                logger.debug(f"✅ Book ({country}, {category}): cache_statusもクリアしました")
            except Exception as e:
                logger.warning(f"⚠️ Book ({country}): cache_statusクリアエラー（処理は継続）: {e}")
            return cache_cleared
        except Exception as e:
            logger.error(f"❌ Book キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count, *args, **kwargs):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Book: cache_status更新エラー: {e}")
            return False
    
    def _generate_amazon_link(self, title, isbn=None, country='JP'):
        """書籍タイトルからAmazonアソシエイトリンクを生成
        
        Args:
            title: 書籍タイトル
            isbn: ISBN（オプション）
            country: 国コード ('JP' または 'US')
        
        Returns:
            str: Amazonアソシエイトリンク、またはNone（アフィリエイトID未設定時）
        """
        if not self.amazon_affiliate_id:
            return None
        
        # 国コードに応じてドメインを決定
        domain = 'amazon.co.jp' if country == 'JP' else 'amazon.com'
        
        # ISBNがあれば使用、なければタイトルで検索
        if isbn:
            # ISBNから直接リンクを生成
            url = f"https://www.{domain}/dp/{isbn}?tag={self.amazon_affiliate_id}"
        else:
            # タイトルで検索
            from urllib.parse import quote
            search_query = quote(title)
            url = f"https://www.{domain}/s?k={search_query}&tag={self.amazon_affiliate_id}"
        
        return url
    
    def _add_rakuten_affiliate(self, url: str) -> str:
        """楽天アイテムURLへaffiliateIdを付与（既存クエリは保持）
        
        Args:
            url: 楽天商品/ブックスのURL
        """
        if not url or not self.rakuten_affiliate_id:
            return url
        
        try:
            from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
            parsed = urlparse(url)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            
            # 既にaffiliateIdが付いていればそのまま
            if 'affiliateId' in query and query['affiliateId']:
                return url
            
            query['affiliateId'] = self.rakuten_affiliate_id
            new_query = urlencode(query, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            # パース失敗時は元URLを返す
            return url
    
    def _fetch_trends(self, country='JP', limit=25, *args, **kwargs):
        """外部APIから書籍データを取得"""
        category = kwargs.get('category', 'all')
        if country == 'JP':
            return self._fetch_rakuten_books_trends(limit, category=category)
        elif country == 'US':
            return self._fetch_google_books_trends(limit, category=category)
        else:
            return {
                'success': False,
                'error': f'サポートされていない国コード: {country}',
                'data': []
            }
    
    def get_trends(self, country='JP', limit=25, force_refresh=False, category='all'):
        """
        書籍トレンドを取得
        
        Args:
            country: 国コード ('JP' または 'US')
            limit: 取得件数
            force_refresh: キャッシュを無視して強制更新
            category: カテゴリ ('all' | 'fiction' | 'business' | 'humanities' | 'practical' for JP;
                        'all' | 'fiction' | 'business' | 'biography' | 'science' for US)
        
        Returns:
            dict: トレンドデータ
        """
        try:
            if self._is_dummy_mode():
                logger.info(f"🎭 Book: ダミーモードが有効です。ダミーデータのみ返却します (country: {country}, category: {category})")
                if force_refresh:
                    try:
                        self._clear_cache(country=country, category=category)
                    except Exception as e:
                        logger.warning(f"⚠️ Book: ダミーモード キャッシュクリア中にエラー: {e}")
                cached_data = self._get_from_cache(country=country, category=category)
                if cached_data and len(cached_data) > 0:
                    cached_data.sort(key=lambda x: x.get('rank', 999999))
                    logger.info(f"✅ Book: ダミーキャッシュから {len(cached_data)} 件取得 (country: {country})")
                    return {
                        'success': True,
                        'data': cached_data[:limit],
                        'status': 'dummy_cached',
                        'source': 'dummy_database_cache',
                        'country': country,
                        'category': category,
                        'total_count': len(cached_data),
                    }
                dummy_data = generate_dummy_book_data(country=country, limit=limit)
                try:
                    if self._save_to_cache(dummy_data, country=country, category=category):
                        cache_key = self._get_cache_key(country=country, category=category)
                        self._update_cache_status(cache_key, len(dummy_data))
                        logger.info(f"✅ Book: ダミーデータ {len(dummy_data)} 件をキャッシュに保存しました (country: {country})")
                except Exception as e:
                    logger.warning(f"⚠️ Book: ダミーデータキャッシュ保存中にエラー: {e}")
                return {
                    'success': True,
                    'data': dummy_data[:limit],
                    'status': 'dummy_generated',
                    'source': 'dummy_database_cache',
                    'country': country,
                    'category': category,
                    'total_count': len(dummy_data),
                }
            if country == 'JP':
                return self._get_rakuten_books_trends(limit, force_refresh, category=category)
            elif country == 'US':
                return self._get_google_books_trends(limit, force_refresh, category=category)
            else:
                return {
                    'success': False,
                    'error': f'サポートされていない国コード: {country}',
                    'data': []
                }
                
        except Exception as e:
            logger.error(f"❌ Book トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'書籍トレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _get_rakuten_books_trends(self, limit=25, force_refresh=False, category='all'):
        """楽天ブックスAPIを使用して書籍トレンドを取得（日本向け）"""
        try:
            if not self.rakuten_app_id:
                return {
                    'success': False,
                    'error': 'RAKUTEN_APP_IDが設定されていません',
                    'data': []
                }
            genre_ids = RAKUTEN_BOOK_CATEGORY_GENRES.get(category, RAKUTEN_BOOK_CATEGORY_GENRES['all'])
            if force_refresh:
                logger.info(f"🔄 Book (楽天) force_refresh: キャッシュをクリアします (category: {category})")
                self.db.clear_book_trends_cache('JP', category)
            cached_data = self.db.get_book_trends_from_cache('JP', category)
            if cached_data:
                cached_data.sort(key=lambda x: x.get('rank', 999999))
                if force_refresh:
                    try:
                        self.db.update_cache_status(f'book_trends_JP_{category}', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ Book (楽天): cache_status更新エラー（処理は継続）: {e}")
                logger.info(f"✅ Book (楽天): キャッシュから{len(cached_data)}件のデータを取得しました (category: {category})")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'country': 'JP',
                    'category': category
                }
            if not force_refresh:
                logger.warning("⚠️ Book (楽天): キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                return {
                    'data': [],
                    'status': 'cache_not_found',
                    'source': 'database_cache',
                    'country': 'JP',
                    'category': category,
                    'success': True,
                    'error': 'キャッシュにデータがありません'
                }
            logger.warning("⚠️ Book (楽天): キャッシュデータが見つかりません。外部APIを呼び出します")
            return self._fetch_rakuten_books_trends(limit, category=category)
        except Exception as e:
            logger.error(f"❌ Book (楽天) トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'楽天ブックストレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _rakuten_response_items(self, data):
        """APIレスポンスから商品リストを取得（Items/items の大文字小文字両対応）"""
        return data.get('Items', data.get('items', []))

    def _rakuten_item_payload(self, raw_item):
        """raw_item から1件分の辞書を取得（Item/item の大文字小文字、またはフラット対応）"""
        if isinstance(raw_item, dict):
            inner = raw_item.get('Item', raw_item.get('item'))
            if inner is not None:
                return inner
            # ラップなしで title/itemPrice 等が直で入っている場合
            if raw_item.get('title') is not None or raw_item.get('itemName') is not None or raw_item.get('itemPrice') is not None:
                return raw_item
        return {}

    def _fetch_rakuten_books_trends(self, limit=25, category='all'):
        """楽天ブックスAPIから書籍データを取得（5択カテゴリ対応）"""
        try:
            genre_ids = RAKUTEN_BOOK_CATEGORY_GENRES.get(category, RAKUTEN_BOOK_CATEGORY_GENRES['all'])
            logger.info(f"📚 Book (楽天) API呼び出し開始 (category: {category}, genres: {len(genre_ids)}件)")
            url = self.rakuten_ranking_url
            all_items = []
            seen_keys = set()  # 重複除去用（ISBN or itemUrl）

            # 各ジャンルからデータを取得
            for genre_id in genre_ids:
                params = {
                    'applicationId': self.rakuten_app_id,
                    'format': 'json',
                    'booksGenreId': genre_id,
                    'sort': 'sales',
                    'hits': min(max(limit // len(genre_ids) + 5, 5), 20),
                    'page': 1
                }
                
                if self.rakuten_affiliate_id:
                    params['affiliateId'] = self.rakuten_affiliate_id
                
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'trends-dashboard/1.0.0'
                }
                
                # レート制限をチェック（楽天APIは1秒1回のため共有制限を使用）
                get_rakuten_api_rate_limiter().wait_if_needed()
                
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = self._rakuten_response_items(data)
                        
                        for item in items:
                            item_data = self._rakuten_item_payload(item)
                            isbn = (item_data.get('isbn') or '').strip()
                            item_url = (item_data.get('itemUrl') or '').strip()
                            dedup_key = isbn or item_url or f"{item_data.get('title', '')}|{item_data.get('author', '')}"
                            if not dedup_key or dedup_key in seen_keys:
                                continue
                            seen_keys.add(dedup_key)
                            all_items.append(item)
                            if len(all_items) >= limit * 2:
                                break
                        if len(all_items) >= limit * 2:
                            break
                    else:
                        logger.warning(f"楽天ブックス API エラー (ジャンル: {genre_id}): HTTP {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"楽天ブックス API リクエストエラー (ジャンル: {genre_id}): {e}")
                    continue
            
            # 単一ジャンルで0件のときは総合(001001)をフォールバックで取得
            if not all_items and len(genre_ids) == 1 and genre_ids[0] != '001001':
                fallback_id = '001001'
                logger.info(f"📚 Book (楽天): ジャンル {genre_ids[0]} が0件のため、総合({fallback_id})をフォールバック取得")
                get_rakuten_api_rate_limiter().wait_if_needed()
                try:
                    params = {
                        'applicationId': self.rakuten_app_id,
                        'format': 'json',
                        'booksGenreId': fallback_id,
                        'sort': 'sales',
                        'hits': min(limit + 5, 20),
                        'page': 1
                    }
                    if self.rakuten_affiliate_id:
                        params['affiliateId'] = self.rakuten_affiliate_id
                    response = requests.get(url, params=params, headers={'Accept': 'application/json', 'User-Agent': 'trends-dashboard/1.0.0'}, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        for item in self._rakuten_response_items(data):
                            item_data = self._rakuten_item_payload(item)
                            dedup_key = (item_data.get('isbn') or '').strip() or (item_data.get('itemUrl') or '').strip() or f"{item_data.get('title', '')}|{item_data.get('author', '')}"
                            if dedup_key and dedup_key not in seen_keys:
                                seen_keys.add(dedup_key)
                                all_items.append(item)
                                if len(all_items) >= limit * 2:
                                    break
                except Exception as e:
                    logger.warning(f"楽天ブックス フォールバック取得エラー: {e}")
            
            if not all_items:
                logger.warning("⚠️ Book (楽天): データが取得できませんでした")
                return {
                    'success': False,
                    'error': '書籍データが取得できませんでした',
                    'data': []
                }
            
            # 売上順でソート（salesフィールドで）
            all_items.sort(key=lambda x: self._rakuten_item_payload(x).get('sales', 0), reverse=True)
            
            trends_data = []
            success_count = 0
            error_count = 0
            
            for idx, item in enumerate(all_items[:limit], 1):
                try:
                    item_data = self._rakuten_item_payload(item)
                    
                    # 書籍情報を整形（title/itemName などAPIの表記ゆれに対応）
                    isbn = item_data.get('isbn', '') or ''
                    title = item_data.get('title', '') or item_data.get('itemName', '') or 'タイトル不明'
                    book_data = {
                        'rank': idx,
                        'isbn': isbn,
                        'title': title,
                        'author': item_data.get('author', ''),
                        'publisher': item_data.get('publisherName', ''),
                        'price': item_data.get('itemPrice', 0),
                        'sales': item_data.get('sales', 0),
                        # itemUrlを優先し、affiliateIdが未付与なら付ける
                        'item_url': self._add_rakuten_affiliate(item_data.get('itemUrl', '')),
                        # 楽天APIが返すaffiliateUrlがあれば使い、なければitemUrlを補完
                        'affiliate_url': item_data.get('affiliateUrl', '') or self._add_rakuten_affiliate(item_data.get('itemUrl', '')),
                        'amazon_link': self._generate_amazon_link(
                            title,
                            isbn,
                            'JP'
                        ),
                        'image_url': item_data.get('largeImageUrl', ''),
                        'release_date': item_data.get('salesDate', ''),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    trends_data.append(book_data)
                    success_count += 1
                    
                except Exception as e:
                    logger.warning(f"書籍 {self._rakuten_item_payload(item).get('isbn', 'unknown')} 処理エラー: {str(e)[:100]}")
                    error_count += 1
                    continue
            
            # データベースにキャッシュを保存
            if trends_data:
                self.db.save_book_trends_to_cache(trends_data, 'JP', category)
                logger.info(f"✅ Book (楽天): {len(trends_data)}件のデータを取得し、キャッシュに保存しました (category: {category})")
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'rakuten_books',
                'country': 'JP',
                'category': category
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Book (楽天) API リクエストエラー: {e}")
            return {
                'success': False,
                'error': f'楽天ブックス API リクエストエラー: {str(e)}',
                'data': []
            }
        except Exception as e:
            logger.error(f"❌ Book (楽天) API 処理エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'書籍トレンドの取得に失敗しました: {str(e)}',
                'data': []
            }
    
    def _get_google_books_trends(self, limit=25, force_refresh=False, category='all'):
        """Google Books APIを使用して書籍トレンドを取得（US向け）"""
        try:
            if not self.google_books_api_key:
                return {
                    'success': False,
                    'error': 'GOOGLE_BOOKS_API_KEYが設定されていません',
                    'data': []
                }
            if force_refresh:
                logger.info(f"🔄 Book (Google) force_refresh: キャッシュをクリアします (category: {category})")
                self._clear_cache(country='US', category=category)
            cached_data = self.db.get_book_trends_from_cache('US', category)
            if cached_data is None:
                cached_data = []
            if cached_data and len(cached_data) > 0:
                cached_data.sort(key=lambda x: x.get('rank', 999999))
                if force_refresh:
                    try:
                        self.db.update_cache_status(f'book_trends_US_{category}', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ Book (Google): cache_status更新エラー（処理は継続）: {e}")
                logger.info(f"✅ Book (Google): キャッシュから{len(cached_data)}件のデータを取得しました (category: {category})")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'country': 'US',
                    'category': category
                }
            try:
                cache_info = self.db.get_cache_info(f'book_trends_US_{category}')
                if cache_info and cache_info.get('data_count', 0) > 0:
                    logger.warning("⚠️ Book (Google): cache_statusに記録あり。外部APIを呼び出します")
                    return self._fetch_google_books_trends(limit, category=category)
            except Exception as e:
                logger.warning(f"⚠️ Book (Google): cache_status確認エラー（処理は継続）: {e}")
            if not force_refresh:
                return {
                    'data': [],
                    'status': 'cache_not_found',
                    'source': 'database_cache',
                    'country': 'US',
                    'category': category,
                    'success': True,
                    'error': 'キャッシュにデータがありません'
                }
            logger.warning("⚠️ Book (Google): キャッシュデータが見つかりません。外部APIを呼び出します")
            return self._fetch_google_books_trends(limit, category=category)
        except Exception as e:
            logger.error(f"❌ Book (Google) トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Google Booksトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_google_books_trends(self, limit=25, category='all'):
        """Google Books APIから書籍データを取得（5択カテゴリ対応）"""
        try:
            search_queries = GOOGLE_BOOK_CATEGORY_QUERIES.get(category, GOOGLE_BOOK_CATEGORY_QUERIES['all'])
            logger.info(f"📚 Book (Google) API呼び出し開始 (category: {category})")
            url = f"{self.google_books_base_url}/volumes"
            all_items = []
            max_queries = min(len(search_queries), 4) if category == 'all' else len(search_queries)
            for query in search_queries[:max_queries]:
                params = {
                    'q': query,
                    'orderBy': 'relevance',
                    'maxResults': min(limit * 2, 40),  # 余裕を持たせる
                    'key': self.google_books_api_key,
                    'langRestrict': 'en'  # 英語書籍
                }
                
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'trends-dashboard/1.0.0'
                }
                
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                try:
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get('items', [])
                        if items:
                            all_items.extend(items)
                            logger.debug(f"Google Books API: クエリ '{query}' から {len(items)}件取得")
                    else:
                        logger.warning(f"Google Books API エラー (クエリ: {query}): HTTP {response.status_code}")
                    
                    # 必要な件数に達したら終了（余裕を持たせる）
                    if len(all_items) >= limit * 2:
                        break
                except Exception as e:
                    logger.warning(f"Google Books API リクエストエラー (クエリ: {query}): {e}")
                    continue
            
            # 重複を除去（IDで）
            seen_ids = set()
            unique_items = []
            for item in all_items:
                item_id = item.get('id')
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
            
            # 言語フィルタリングを先に適用
            english_items = []
            for item in unique_items:
                volume_info = item.get('volumeInfo', {})
                book_language = volume_info.get('language', '').lower()
                if not book_language or book_language in ['en', 'en-us', 'en-gb']:
                    english_items.append(item)
            
            items = english_items[:limit * 2]  # 余裕を持たせる
            
            if not items:
                logger.warning("⚠️ Book (Google): データが取得できませんでした")
                return {
                    'success': False,
                    'error': '書籍データが取得できませんでした',
                    'data': []
                }
            
            trends_data = []
            success_count = 0
            error_count = 0
            
            # 評価順でソート（評価の高い順）
            items.sort(key=lambda x: x.get('volumeInfo', {}).get('averageRating', 0), reverse=True)
            
            for idx, volume in enumerate(items[:limit], 1):
                try:
                    volume_info = volume.get('volumeInfo', {})
                    sale_info = volume.get('saleInfo', {})
                    
                    # ISBNを取得（Amazonリンク生成用）
                    isbn = None
                    industry_identifiers = volume_info.get('industryIdentifiers', [])
                    if industry_identifiers:
                        # ISBN-13を優先、なければISBN-10を使用
                        for identifier in industry_identifiers:
                            if identifier.get('type') == 'ISBN_13':
                                isbn = identifier.get('identifier')
                                break
                        if not isbn:
                            for identifier in industry_identifiers:
                                if identifier.get('type') == 'ISBN_10':
                                    isbn = identifier.get('identifier')
                                    break
                    
                    # 書籍情報を整形（言語フィルタリングは既に適用済み）
                    book_data = {
                        'rank': idx,
                        'id': volume.get('id', ''),
                        'title': volume_info.get('title', 'タイトル不明'),
                        'subtitle': volume_info.get('subtitle', ''),
                        'authors': volume_info.get('authors', []),
                        'publisher': volume_info.get('publisher', ''),
                        'published_date': volume_info.get('publishedDate', ''),
                        'description': volume_info.get('description', ''),
                        'page_count': volume_info.get('pageCount', 0),
                        'categories': volume_info.get('categories', []),
                        'average_rating': volume_info.get('averageRating', 0),
                        'ratings_count': volume_info.get('ratingsCount', 0),
                        'language': volume_info.get('language', ''),
                        'preview_link': volume_info.get('previewLink', ''),
                        'info_link': volume_info.get('infoLink', ''),
                        'image_links': volume_info.get('imageLinks', {}),
                        'price': sale_info.get('retailPrice', {}).get('amount', 0),
                        'currency': sale_info.get('retailPrice', {}).get('currencyCode', 'USD'),
                        'buy_link': sale_info.get('buyLink', ''),
                        'amazon_link': self._generate_amazon_link(
                            volume_info.get('title', ''),
                            isbn,
                            'US'
                        ),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # 画像URLを取得
                    image_links = book_data.get('image_links', {})
                    book_data['thumbnail'] = image_links.get('thumbnail', '')
                    book_data['small_thumbnail'] = image_links.get('smallThumbnail', '')
                    book_data['medium'] = image_links.get('medium', '')
                    book_data['large'] = image_links.get('large', '')
                    # サムネイル画像URLを設定（優先順位: medium > thumbnail > small_thumbnail）
                    book_data['image_url'] = image_links.get('medium', '') or image_links.get('thumbnail', '') or image_links.get('smallThumbnail', '')
                    
                    trends_data.append(book_data)
                    success_count += 1
                    
                except Exception as e:
                    logger.warning(f"書籍 {volume.get('id', 'unknown')} 処理エラー: {str(e)[:100]}")
                    error_count += 1
                    continue
            
            if trends_data:
                self.db.save_book_trends_to_cache(trends_data, 'US', category)
                logger.info(f"✅ Book (Google): {len(trends_data)}件のデータを取得し、キャッシュに保存しました (category: {category})")
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'google_books',
                'country': 'US',
                'category': category
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Book (Google) API リクエストエラー: {e}")
            return {
                'success': False,
                'error': f'Google Books API リクエストエラー: {str(e)}',
                'data': []
            }
        except Exception as e:
            logger.error(f"❌ Book (Google) API 処理エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'書籍トレンドの取得に失敗しました: {str(e)}',
                'data': []
            }

