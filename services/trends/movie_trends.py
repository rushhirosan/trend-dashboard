"""
映画トレンド関連の処理を管理するモジュール
TMDB (The Movie Database) APIを使用してトレンド映画を取得
"""

import os
import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class MovieTrendsManager:
    """映画トレンドの管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = os.getenv('TMDB_API_KEY')
        self.db = TrendsCache()
        # レート制限: TMDB APIは40リクエスト/10秒（保守的に10リクエスト/分に設定）
        self.rate_limiter = get_rate_limiter('movie', max_requests=10, window_seconds=60)
        
        if not self.api_key:
            logger.warning("⚠️ TMDB_API_KEYが設定されていません。TMDB APIは使用できません。")
        else:
            logger.info("Movie Trends Manager初期化完了")
            logger.info(f"  Base URL: {self.base_url}")
    
    def get_trends(self, country='JP', time_window='day', limit=25, force_refresh=False):
        """
        映画トレンドを取得（TMDBのトレンド検索）
        
        Args:
            country: 国コード ('JP' または 'US')
            time_window: 期間 ('day' または 'week')
            limit: 取得件数
            force_refresh: キャッシュを無視して強制更新
        
        Returns:
            dict: トレンドデータ
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'error': 'TMDB_API_KEYが設定されていません',
                    'data': []
                }
            
            # 言語設定（国コードに基づく）
            language = 'en-US' if country == 'US' else 'ja-JP'
            
            if force_refresh:
                logger.info(f"🔄 Movie force_refresh: キャッシュをクリアします (country: {country})")
                self.db.clear_movie_trends_cache(country=country)
            
            # キャッシュからデータを取得（国コードでフィルタ）
            cached_data = self.db.get_movie_trends_from_cache(country=country)
            
            if cached_data:
                # 人気度順でソート（popularityの降順）
                cached_data.sort(key=lambda x: x.get('popularity', 0), reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                logger.info(f"✅ Movie: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache'
                }
            else:
                logger.warning(f"⚠️ Movie: キャッシュデータが見つかりません。外部APIを呼び出します (country: {country})")
                return self._fetch_trending_movies(country, time_window, limit)
                
        except Exception as e:
            logger.error(f"❌ Movie トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'映画トレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def _fetch_trending_movies(self, country='JP', time_window='day', limit=25):
        """TMDB APIを使用してトレンド映画を取得（ページネーション対応）"""
        try:
            # 言語設定（国コードに基づく）
            language = 'en-US' if country == 'US' else 'ja-JP'
            
            logger.info(f"🎬 Movie API呼び出し開始（country: {country}, language: {language}, 期間: {time_window}, 取得件数: {limit}）")
            
            # TMDB APIは1ページあたり最大20件
            # 25件取得する場合は2ページ目も取得する必要がある
            pages_needed = (limit + 19) // 20  # 切り上げ計算
            all_results = []
            
            for page in range(1, pages_needed + 1):
                # TMDBのトレンドエンドポイント
                url = f"{self.base_url}/trending/movie/{time_window}"
                
                params = {
                    'api_key': self.api_key,
                    'language': language,  # 国コードに基づいて言語を設定
                    'page': page
                }
                
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'trends-dashboard/1.0.0'
                }
                
                # レート制限をチェック
                self.rate_limiter.wait_if_needed()
                
                logger.debug(f"TMDB API リクエスト: page={page}")
                response = requests.get(url, params=params, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    logger.error(f"❌ TMDB API エラー: HTTP {response.status_code} (page {page})")
                    logger.error(f"レスポンス: {response.text[:200]}")
                    if page == 1:
                        # 1ページ目でエラーなら全体を失敗とする
                        return {
                            'success': False,
                            'error': f'TMDB API エラー: {response.status_code}',
                            'data': []
                        }
                    else:
                        # 2ページ目以降でエラーなら、取得できた分だけ返す
                        break
                
                data = response.json()
                page_results = data.get('results', [])
                
                if not page_results:
                    logger.warning(f"⚠️ Movie: ページ{page}でデータが取得できませんでした")
                    break
                
                all_results.extend(page_results)
                
                # 必要な件数に達したら終了
                if len(all_results) >= limit:
                    break
            
            if not all_results:
                logger.warning("⚠️ Movie: データが取得できませんでした")
                return {
                    'success': False,
                    'error': '映画データが取得できませんでした',
                    'data': []
                }
            
            trends_data = []
            success_count = 0
            error_count = 0
            
            for idx, movie in enumerate(all_results[:limit], 1):
                try:
                    # 映画情報を整形
                    movie_data = {
                        'rank': idx,
                        'id': movie.get('id'),
                        'title': movie.get('title', 'タイトル不明'),
                        'original_title': movie.get('original_title', ''),
                        'overview': movie.get('overview', ''),
                        'popularity': movie.get('popularity', 0),
                        'vote_average': movie.get('vote_average', 0),
                        'vote_count': movie.get('vote_count', 0),
                        'release_date': movie.get('release_date', ''),
                        'poster_path': movie.get('poster_path', ''),
                        'backdrop_path': movie.get('backdrop_path', ''),
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # ポスター画像URLを生成（TMDBの画像ベースURL）
                    if movie_data['poster_path']:
                        movie_data['poster_url'] = f"https://image.tmdb.org/t/p/w500{movie_data['poster_path']}"
                    else:
                        movie_data['poster_url'] = None
                    
                    if movie_data['backdrop_path']:
                        movie_data['backdrop_url'] = f"https://image.tmdb.org/t/p/w1280{movie_data['backdrop_path']}"
                    else:
                        movie_data['backdrop_url'] = None
                    
                    trends_data.append(movie_data)
                    success_count += 1
                    
                except Exception as e:
                    logger.warning(f"映画 {movie.get('id', 'unknown')} 処理エラー: {str(e)[:100]}")
                    error_count += 1
                    continue
            
            # データベースにキャッシュを保存（国コードを含める）
            if trends_data:
                # 各データに国コードを追加
                for item in trends_data:
                    item['country'] = country
                self.db.save_movie_trends_to_cache(trends_data, country=country)
                logger.info(f"✅ Movie: {len(trends_data)}件のデータを取得し、キャッシュに保存しました (country: {country}, 成功: {success_count}, エラー: {error_count})")
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'api_fetched',
                'source': 'tmdb'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Movie API リクエストエラー: {e}")
            return {
                'success': False,
                'error': f'TMDB API リクエストエラー: {str(e)}',
                'data': []
            }
        except Exception as e:
            logger.error(f"❌ Movie API 処理エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'映画トレンドの取得に失敗しました: {str(e)}',
                'data': []
            }

