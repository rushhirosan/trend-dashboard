"""
書籍トレンド関連の処理を管理するモジュール
楽天ブックスAPI（日本）とGoogle Books API（US）を使用して書籍トレンドを取得
"""

import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class BookTrendsManager:
    """書籍トレンドの管理クラス"""
    
    def __init__(self):
        """初期化"""
        # 楽天ブックスAPI設定（日本向け）
        # 書籍ジャンル一覧: https://webservice.rakuten.co.jp/api/booksgenreidsearch/
        # 001001: 本・雑誌（総合）
        self.rakuten_base_url = "https://app.rakuten.co.jp/services/api/BooksTotal/Search/20170404"
        self.rakuten_ranking_url = "https://app.rakuten.co.jp/services/api/BooksBook/Search/20170404"
        self.rakuten_app_id = os.getenv('RAKUTEN_APP_ID')
        self.rakuten_affiliate_id = os.getenv('RAKUTEN_AFFILIATE_ID')
        
        # Google Books API設定（US向け）
        self.google_books_base_url = "https://www.googleapis.com/books/v1"
        self.google_books_api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
        
        self.db = TrendsCache()
        # レート制限: 楽天APIは1リクエスト/秒、Google Books APIは1000リクエスト/日（保守的に10リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('book', max_requests=10, window_seconds=60)
        
        logger.info("Book Trends Manager初期化完了")
        logger.info(f"  楽天ブックス App ID: {'設定済み' if self.rakuten_app_id else '未設定'}")
        logger.info(f"  Google Books API Key: {'設定済み' if self.google_books_api_key else '未設定'}")
    
    def get_trends(self, country='JP', limit=25, force_refresh=False):
        """
        書籍トレンドを取得
        
        Args:
            country: 国コード ('JP' または 'US')
            limit: 取得件数
            force_refresh: キャッシュを無視して強制更新
        
        Returns:
            dict: トレンドデータ
        """
        try:
            if country == 'JP':
                return self._get_rakuten_books_trends(limit, force_refresh)
            elif country == 'US':
                return self._get_google_books_trends(limit, force_refresh)
            else:
                return {
                    'success': False,
                    'error': f'サポートされていない国コード: {country}',
                    'data': []
                }
                
        except Exception as e:
            logger.error(f"❌ Book トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'書籍トレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _get_rakuten_books_trends(self, limit=25, force_refresh=False):
        """楽天ブックスAPIを使用して書籍トレンドを取得（日本向け）"""
        try:
            if not self.rakuten_app_id:
                return {
                    'success': False,
                    'error': 'RAKUTEN_APP_IDが設定されていません',
                    'data': []
                }
            
            if force_refresh:
                logger.info(f"🔄 Book (楽天) force_refresh: キャッシュをクリアします")
                self.db.clear_book_trends_cache('JP')
            
            # キャッシュからデータを取得
            cached_data = self.db.get_book_trends_from_cache('JP')
            
            if cached_data:
                # ランキング順でソート
                cached_data.sort(key=lambda x: x.get('rank', 999999))
                
                logger.info(f"✅ Book (楽天): キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'country': 'JP'
                }
            else:
                logger.warning("⚠️ Book (楽天): キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_rakuten_books_trends(limit)
                
        except Exception as e:
            logger.error(f"❌ Book (楽天) トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'楽天ブックストレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_rakuten_books_trends(self, limit=25):
        """楽天ブックスAPIから書籍データを取得（漫画を除外）"""
        try:
            logger.info(f"📚 Book (楽天) API呼び出し開始（漫画除外）")
            
            # 楽天ブックスAPI: 複数のジャンルIDから取得してマージ
            # 漫画（001016）を除外し、以下のジャンルから取得:
            # 001002: 小説・エッセイ
            # 001003: ビジネス・経済
            # 001004: 人文・思想
            # 001005: 社会・政治
            # 001006: 歴史・地理
            # 001007: 科学・技術
            # 001008: 医学・薬学
            # 001009: コンピュータ・IT
            # 001010: 趣味・実用
            genre_ids = [
                '001002',  # 小説・エッセイ
                '001003',  # ビジネス・経済
                '001004',  # 人文・思想
                '001005',  # 社会・政治
                '001006',  # 歴史・地理
                '001007',  # 科学・技術
                '001008',  # 医学・薬学
                '001009',  # コンピュータ・IT
                '001010'   # 趣味・実用
            ]
            
            url = self.rakuten_ranking_url
            all_items = []
            seen_isbns = set()  # 重複除去用
            
            # 各ジャンルからデータを取得
            for genre_id in genre_ids:
                params = {
                    'applicationId': self.rakuten_app_id,
                    'format': 'json',
                    'booksGenreId': genre_id,
                    'sort': 'sales',  # 売上順
                    'hits': min(limit // len(genre_ids) + 5, 20),  # ジャンルごとに取得（余裕を持たせる）
                    'page': 1
                }
                
                if self.rakuten_affiliate_id:
                    params['affiliateId'] = self.rakuten_affiliate_id
                
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
                        items = data.get('Items', [])
                        
                        for item in items:
                            item_data = item.get('Item', {})
                            isbn = item_data.get('isbn', '')
                            
                            # 重複チェック
                            if isbn and isbn not in seen_isbns:
                                seen_isbns.add(isbn)
                                all_items.append(item)
                                
                                # 必要な件数に達したら終了
                                if len(all_items) >= limit * 2:  # 余裕を持たせる
                                    break
                        
                        if len(all_items) >= limit * 2:
                            break
                    else:
                        logger.warning(f"楽天ブックス API エラー (ジャンル: {genre_id}): HTTP {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"楽天ブックス API リクエストエラー (ジャンル: {genre_id}): {e}")
                    continue
            
            if not all_items:
                logger.warning("⚠️ Book (楽天): データが取得できませんでした")
                return {
                    'success': False,
                    'error': '書籍データが取得できませんでした',
                    'data': []
                }
            
            # 売上順でソート（salesフィールドで）
            all_items.sort(key=lambda x: x.get('Item', {}).get('sales', 0), reverse=True)
            
            trends_data = []
            success_count = 0
            error_count = 0
            
            for idx, item in enumerate(all_items[:limit], 1):
                try:
                    item_data = item.get('Item', {})
                    
                    # 書籍情報を整形
                    book_data = {
                        'rank': idx,
                        'isbn': item_data.get('isbn', ''),
                        'title': item_data.get('title', 'タイトル不明'),
                        'author': item_data.get('author', ''),
                        'publisher': item_data.get('publisherName', ''),
                        'price': item_data.get('itemPrice', 0),
                        'sales': item_data.get('sales', 0),
                        'item_url': item_data.get('itemUrl', ''),
                        'affiliate_url': item_data.get('affiliateUrl', ''),
                        'image_url': item_data.get('largeImageUrl', ''),
                        'release_date': item_data.get('salesDate', ''),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    trends_data.append(book_data)
                    success_count += 1
                    
                except Exception as e:
                    logger.warning(f"書籍 {item.get('Item', {}).get('isbn', 'unknown')} 処理エラー: {str(e)[:100]}")
                    error_count += 1
                    continue
            
            # データベースにキャッシュを保存
            if trends_data:
                self.db.save_book_trends_to_cache(trends_data, 'JP')
                logger.info(f"✅ Book (楽天): {len(trends_data)}件のデータを取得し、キャッシュに保存しました (成功: {success_count}, エラー: {error_count})")
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'rakuten_books',
                'country': 'JP'
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
    
    def _get_google_books_trends(self, limit=25, force_refresh=False):
        """Google Books APIを使用して書籍トレンドを取得（US向け）"""
        try:
            if not self.google_books_api_key:
                return {
                    'success': False,
                    'error': 'GOOGLE_BOOKS_API_KEYが設定されていません',
                    'data': []
                }
            
            if force_refresh:
                logger.info(f"🔄 Book (Google) force_refresh: キャッシュをクリアします")
                self.db.clear_book_trends_cache('US')
            
            # キャッシュからデータを取得
            cached_data = self.db.get_book_trends_from_cache('US')
            
            if cached_data:
                # ランキング順でソート
                cached_data.sort(key=lambda x: x.get('rank', 999999))
                
                logger.info(f"✅ Book (Google): キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    'country': 'US'
                }
            else:
                logger.warning("⚠️ Book (Google): キャッシュデータが見つかりません。外部APIを呼び出します")
                return self._fetch_google_books_trends(limit)
                
        except Exception as e:
            logger.error(f"❌ Book (Google) トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Google Booksトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_google_books_trends(self, limit=25):
        """Google Books APIから書籍データを取得"""
        try:
            logger.info(f"📚 Book (Google) API呼び出し開始")
            
            # Google Books API: ベストセラーや人気書籍を取得
            # 人気のある書籍を取得するため、複数の検索クエリを試行
            url = f"{self.google_books_base_url}/volumes"
            
            # 人気書籍を取得するための検索クエリ
            # 複数のキーワードで検索して、評価の高い書籍を取得
            # 英語書籍のみを取得するため、langRestrictパラメータを使用
            search_queries = [
                'subject:fiction',
                'subject:nonfiction',
                'subject:bestseller',
                'subject:popular',
                'subject:business',
                'subject:science'
            ]
            
            all_items = []
            
            # 複数の検索クエリから書籍を取得（より多くのクエリを使用）
            for query in search_queries[:4]:  # 最初の4つのクエリを使用
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
            
            # データベースにキャッシュを保存
            if trends_data:
                self.db.save_book_trends_to_cache(trends_data, 'US')
                logger.info(f"✅ Book (Google): {len(trends_data)}件のデータを取得し、キャッシュに保存しました (成功: {success_count}, エラー: {error_count})")
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'google_books',
                'country': 'US'
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

