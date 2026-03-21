"""
トレンド関連のルート
各トレンドカテゴリのAPIエンドポイント
"""

from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

# Blueprintを作成
trend_bp = Blueprint('trends', __name__, url_prefix='/api')

def get_managers():
    """マネージャーを取得（app.configから取得、フォールバックで空の辞書）"""
    try:
        app = current_app._get_current_object() if hasattr(current_app, '_get_current_object') else current_app
        if app and hasattr(app, 'config'):
            managers = app.config.get('TREND_MANAGERS')
            if managers:
                return managers
    except RuntimeError:
        # Flaskアプリケーションコンテキスト外の場合は無視
        pass
    except Exception as e:
        logger.debug(f"app.configからのマネージャー取得をスキップ: {e}")
    
    # フォールバック：空の辞書を返す（エラーハンドリングはrequire_managerで行う）
    return {}


def get_force_refresh():
    """force_refreshパラメータを取得"""
    return request.args.get('force_refresh', 'false').lower() == 'true'


def require_manager(manager_key):
    """
    マネージャーの存在チェックデコレータ
    
    Args:
        manager_key: managers辞書のキー
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            managers = get_managers()
            manager = managers.get(manager_key)
            if not manager:
                manager_name = manager_key.replace('_', ' ').title()
                logger.error(f"❌ {manager_name} Managerが初期化されていません（利用可能なマネージャー: {list(managers.keys())}）")
                return jsonify({
                    'success': False,
                    'error': f'{manager_name} Managerが初期化されていません'
                }), 500
            return func(*args, manager=manager, **kwargs)
        return wrapper
    return decorator


def handle_trend_response(result, error_message, default_source=None, **extra_fields):
    """
    トレンドAPIのレスポンスを統一フォーマットで返す
    
    Args:
        result: マネージャーから返された結果
        error_message: エラーメッセージのテンプレート
        default_source: デフォルトのソース名
        **extra_fields: レスポンスに追加するフィールド
    """
    # リストが直接返された場合（後方互換性のため）
    if isinstance(result, list):
        return jsonify({
            'success': True,
            'data': result,
            'status': 'fresh',
            **extra_fields
        })
    
    # 辞書形式の結果
    if isinstance(result, dict):
        # successフィールドがFalseの場合
        if not result.get('success', True):
            # キャッシュが見つからない場合は、エラーではなく正常なレスポンスとして扱う（200 OK）
            status = result.get('status', '')
            if status == 'cache_not_found':
                return jsonify({
                    'success': True,
                    'data': result.get('data', []),
                    'status': status,
                    'source': result.get('source', default_source),
                    'message': result.get('error', 'キャッシュにデータがありません'),
                    **extra_fields
                }), 200
            
            # その他のエラーは500エラーとして返す
            error_response = {
                'success': False,
                'error': result.get('error', 'Unknown error')
            }
            # 追加情報がある場合は含める
            for key in ['status_code', 'suggestion', 'response_text', 'status', 'source']:
                if key in result:
                    error_response[key] = result[key]
            
            status_code = result.get('status_code', 500)
            return jsonify(error_response), status_code
        
        # 成功レスポンス
        response = {
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            **extra_fields
        }
        
        # ソース情報を追加
        if 'source' in result:
            response['source'] = result['source']
        elif default_source:
            response['source'] = default_source
        
        # 結果から追加フィールドをコピー
        for key in ['country', 'region', 'region_code', 'category', 'trend_type', 
                   'subreddit', 'story_type', 'sort', 'service', 'genre_id', 'lang']:
            if key in result:
                response[key] = result[key]
        
        return jsonify(response)
    
    # 予期しない形式
    return jsonify({
        'success': False,
        'error': '予期しないレスポンス形式'
    }), 500


def handle_api_error(api_name, error):
    """
    APIエラーを統一フォーマットで処理
    
    Args:
        api_name: API名
        error: エラーオブジェクト
    """
    logger.error(f"❌ {api_name} API エラー: {error}", exc_info=True)
    return jsonify({
        'success': False,
        'error': f'{api_name}の取得に失敗しました: {str(error)}'
    }), 500


@trend_bp.route('/google-trends')
@require_manager('google')
def get_google_trends(manager):
    """Google Trends APIエンドポイント"""
    try:
        country = request.args.get('country', 'JP')
        force_refresh = get_force_refresh()
        
        logger.info(f"📊 Google Trends API呼び出し: country={country}, force_refresh={force_refresh}")

        result = manager.get_trends(region=country, force_refresh=force_refresh)
        logger.info(f"✅ Google Trends API成功: result keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        return handle_trend_response(result, 'Google Trends', 'Google Trends', country=country)

    except Exception as e:
        logger.error(f"❌ Google Trends APIエラー: {e}", exc_info=True)
        return handle_api_error('Google Trends', e)


@trend_bp.route('/youtube-trends')
@require_manager('youtube')
def get_youtube_trends(manager):
    """YouTube Trends APIエンドポイント"""
    try:
        region = request.args.get('region', 'JP')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(region, force_refresh=force_refresh)
        return handle_trend_response(result, 'YouTube Trends', 'YouTube Data API', region_code=region)
        
    except Exception as e:
        return handle_api_error('YouTube Trends', e)


@trend_bp.route('/youtube-rising-trends')
@require_manager('youtube')
def get_youtube_rising_trends(manager):
    """YouTube急上昇 APIエンドポイント"""
    try:
        region = request.args.get('region', 'JP')
        force_refresh = get_force_refresh()
        
        result = manager.get_rising_trends(region, force_refresh=force_refresh)
        return handle_trend_response(result, 'YouTube急上昇', 'YouTube Data API', region_code=region)
        
    except Exception as e:
        return handle_api_error('YouTube急上昇', e)


@trend_bp.route('/music-trends')
@require_manager('music')
def get_music_trends(manager):
    """音楽トレンド APIエンドポイント"""
    try:
        service = request.args.get('service', 'spotify')
        region = request.args.get('region', 'JP')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(service, region, force_refresh=force_refresh)
        return handle_trend_response(result, '音楽トレンド', 'Music API', 
                                    service=service, region=region)
        
    except Exception as e:
        return handle_api_error('音楽トレンド', e)


@trend_bp.route('/worldnews-trends')
@require_manager('worldnews')
def get_worldnews_trends(manager):
    """World News APIエンドポイント"""
    try:
        country = request.args.get('country', 'jp')
        category = request.args.get('category', 'general')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(country, category, force_refresh=force_refresh)
        return handle_trend_response(result, 'World News', 'World News API',
                                    country=country, category=category)
        
    except Exception as e:
        return handle_api_error('World News', e)


@trend_bp.route('/podcast-trends')
@require_manager('podcast')
def get_podcast_trends(manager):
    """ポッドキャストトレンド APIエンドポイント"""
    try:
        trend_type = request.args.get('trend_type', 'best_podcasts')
        region = request.args.get('region', 'jp')
        genre_id = request.args.get('genre_id', None)
        page_size = int(request.args.get('page_size', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(trend_type, genre_id, region, page_size, force_refresh)
        return handle_trend_response(result, 'ポッドキャストトレンド', 'Podcast API',
                                    trend_type=trend_type, region=region)
        
    except Exception as e:
        return handle_api_error('ポッドキャストトレンド', e)


@trend_bp.route('/podcast-genres')
@require_manager('podcast')
def get_podcast_genres(manager):
    """ポッドキャストのジャンル一覧を返す API エンドポイント（Listen Notes genres）"""
    try:
        genres = manager.get_genres() or []
        return jsonify({
            'success': True,
            'data': genres
        })
    except Exception as e:
        return handle_api_error('ポッドキャストジャンル', e)


@trend_bp.route('/rakuten-trends')
@require_manager('rakuten')
def get_rakuten_trends(manager):
    """楽天トレンド APIエンドポイント"""
    try:
        genre_id = request.args.get('genre_id', 'all')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(genre_id, force_refresh=force_refresh)
        return handle_trend_response(result, '楽天トレンド', 'Rakuten API', genre_id=genre_id)
        
    except Exception as e:
        return handle_api_error('楽天トレンド', e)


@trend_bp.route('/hatena-trends')
def get_hatena_trends():
    """はてなブックマークトレンド APIエンドポイント"""
    try:
        # パラメータ取得
        category = request.args.get('category', 'all')
        limit = int(request.args.get('limit', 25))
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        managers = get_managers()
        if not managers.get('hatena'):
            logger.warning("⚠️ Hatena Managerが初期化されていません")
            return jsonify({
                'success': False,
                'data': [],
                'status': 'manager_not_initialized',
                'error': 'Hatena Managerが初期化されていません'
            }), 200  # 500ではなく200を返す（フロントエンドでエラーハンドリング）
        
        result = managers['hatena'].get_trends(category=category, limit=limit, force_refresh=force_refresh)
        
        # エラーが含まれている場合でも、空のデータを返す（500エラーを防ぐ）
        if not result.get('success', True):
            logger.warning(f"⚠️ Hatena: データ取得に失敗しましたが、空のデータを返します: {result.get('error', 'Unknown error')}")
            return jsonify({
                'success': True,  # エラーではなく、データがない状態として扱う
                'data': [],
                'status': result.get('status', 'api_error'),
                'category': category,
                'source': 'Hatena API',
                'message': result.get('error', 'データを取得できませんでした')
            }), 200
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'category': result.get('category', category),
            'source': result.get('source', 'Hatena API')
        })
        
    except Exception as e:
        logger.error(f"❌ Hatena API エラー: {e}", exc_info=True)
        # 500エラーではなく、空のデータを返す（フロントエンドでエラーハンドリング）
        return jsonify({
            'success': True,  # エラーではなく、データがない状態として扱う
            'data': [],
            'status': 'api_error',
            'category': category,
            'error': f'はてなブックマークトレンドの取得に失敗しました: {str(e)}'
        }), 200


@trend_bp.route('/openalex-trends')
@require_manager('openalex')
def get_openalex_trends(manager):
    """OpenAlex学術論文トレンド APIエンドポイント"""
    try:
        category = request.args.get('category', 'trending')
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()

        result = manager.get_trends(category=category, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'OpenAlexトレンド', 'OpenAlex API', category=category)

    except Exception as e:
        return handle_api_error('OpenAlexトレンド', e)


@trend_bp.route('/bluesky-trends')
@require_manager('bluesky')
def get_bluesky_trends(manager):
    """Blueskyトレンド APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()

        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Blueskyトレンド', 'Bluesky API')

    except Exception as e:
        return handle_api_error('Blueskyトレンド', e)


@trend_bp.route('/twitch-trends')
@require_manager('twitch')
def get_twitch_trends(manager):
    """Twitchトレンド APIエンドポイント"""
    try:
        category = request.args.get('type', 'games')  # typeパラメータでカテゴリを指定
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(category=category, limit=limit, force_refresh=force_refresh)
        # trend_typeはresultから取得、なければcategoryを使用
        trend_type = category
        if isinstance(result, dict):
            trend_type = result.get('trend_type', category)
        
        return handle_trend_response(result, 'Twitchトレンド', 'Twitch API', trend_type=trend_type)
        
    except Exception as e:
        return handle_api_error('Twitchトレンド', e)


@trend_bp.route('/reddit-trends')
@require_manager('reddit')
def get_reddit_trends(manager):
    """Reddit Trends APIエンドポイント"""
    try:
        subreddit = request.args.get('subreddit', 'all')
        limit = int(request.args.get('limit', 25))
        time_filter = request.args.get('time_filter', 'day')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(subreddit, limit, time_filter, force_refresh)
        return handle_trend_response(result, 'Redditトレンド', 'Reddit API', subreddit=subreddit)
        
    except Exception as e:
        return handle_api_error('Redditトレンド', e)


@trend_bp.route('/hackernews-trends')
@require_manager('hackernews')
def get_hackernews_trends(manager):
    """Hacker News Trends APIエンドポイント"""
    try:
        story_type = request.args.get('type', 'top')
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(story_type, limit, force_refresh)
        return handle_trend_response(result, 'Hacker Newsトレンド', 'Hacker News API',
                                    story_type=story_type)
        
    except Exception as e:
        return handle_api_error('Hacker Newsトレンド', e)


@trend_bp.route('/qiita-trends')
@require_manager('qiita')
def get_qiita_trends(manager):
    """Qiita Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        sort = request.args.get('sort', 'likes_count')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, sort=sort, force_refresh=force_refresh)
        return handle_trend_response(result, 'Qiitaトレンド', 'Qiita API', sort=sort)
        
    except Exception as e:
        return handle_api_error('Qiitaトレンド', e)


@trend_bp.route('/github-trends')
@require_manager('github')
def get_github_trends(manager):
    """GitHub Trends APIエンドポイント"""
    try:
        language = request.args.get('language', 'all')
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(language=language, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'GitHubトレンド', 'GitHub API', language=language)
        
    except Exception as e:
        return handle_api_error('GitHubトレンド', e)


@trend_bp.route('/appstore-trends')
@require_manager('appstore')
def get_appstore_trends(manager):
    """App Store Trends APIエンドポイント"""
    try:
        country = request.args.get('country', 'JP')
        category = request.args.get('category', 'all')
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(country=country, category=category, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'App Storeトレンド', 'App Store API', country=country, category=category)
        
    except Exception as e:
        return handle_api_error('App Storeトレンド', e)

@trend_bp.route('/nhk-trends')
@require_manager('nhk')
def get_nhk_trends(manager):
    """NHK ニュース APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'NHKニュース', 'NHK RSS')
        
    except Exception as e:
        return handle_api_error('NHKニュース', e)


@trend_bp.route('/news-bundle')
def get_news_bundle():
    """
    NHK + World News を1リクエストでまとめて返す。
    画面更新時に同時表示するため、遅延のばらつきを解消する。
    """
    from concurrent.futures import ThreadPoolExecutor
    try:
        managers = get_managers()
        nhk_mgr = managers.get('nhk')
        worldnews_mgr = managers.get('worldnews')
        force_refresh = get_force_refresh()

        nhk_result = {'success': False, 'data': [], 'error': 'NHK Managerが初期化されていません'}
        worldnews_result = {'success': False, 'data': [], 'error': 'World News Managerが初期化されていません'}

        def fetch_nhk():
            if nhk_mgr:
                try:
                    return nhk_mgr.get_trends(limit=25, force_refresh=force_refresh)
                except Exception as e:
                    logger.exception('NHK取得エラー: %s', e)
                    return {'success': False, 'data': [], 'error': str(e)}
            return nhk_result

        def fetch_worldnews():
            if worldnews_mgr:
                try:
                    return worldnews_mgr.get_trends(country='jp', category='general', force_refresh=force_refresh)
                except Exception as e:
                    logger.exception('World News取得エラー: %s', e)
                    return {'success': False, 'data': [], 'error': str(e)}
            return worldnews_result

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_nhk = executor.submit(fetch_nhk)
            fut_worldnews = executor.submit(fetch_worldnews)
            nhk_result = fut_nhk.result()
            worldnews_result = fut_worldnews.result()

        # handle_trend_response形式に正規化（dataキーを確実に持つ）
        def normalize(r):
            if isinstance(r, dict) and 'data' in r:
                return r
            if isinstance(r, dict) and 'success' in r:
                return r
            if isinstance(r, list):
                return {'success': True, 'data': r, 'status': 'cached'}
            return {'success': False, 'data': [], 'error': '不正なレスポンス'}

        return jsonify({
            'success': True,
            'nhk': normalize(nhk_result),
            'worldnews': normalize(worldnews_result)
        })
    except Exception as e:
        logger.exception('news-bundle エラー: %s', e)
        return jsonify({
            'success': False,
            'nhk': {'success': False, 'data': [], 'error': str(e)},
            'worldnews': {'success': False, 'data': [], 'error': str(e)}
        }), 500


@trend_bp.route('/prtimes-trends')
@require_manager('prtimes')
def get_prtimes_trends(manager):
    """PR TIMES プレスリリース APIエンドポイント（日本向け）"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'PR TIMES', 'PR TIMES RSS')
        
    except Exception as e:
        return handle_api_error('PR TIMES', e)


@trend_bp.route('/prtimes-hatena-trends')
@require_manager('prtimes_hatena')
def get_prtimes_hatena_trends(manager):
    """PR TIMES × はてなブックマーク（7日以内・ブクマ数>0・Top5）APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 5))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'PR TIMES × はてブ', 'PR TIMES RSS + Hatena Count API')
        
    except Exception as e:
        return handle_api_error('PR TIMES × はてブ', e)


@trend_bp.route('/globenewswire-trends')
@require_manager('globenewswire')
def get_globenewswire_trends(manager):
    """GlobeNewswire プレスリリース APIエンドポイント（US向け）"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'GlobeNewswire', 'GlobeNewswire RSS')
        
    except Exception as e:
        return handle_api_error('GlobeNewswire', e)


@trend_bp.route('/globenewswire-market-reaction-trends')
@require_manager('globenewswire_market_reaction')
def get_globenewswire_market_reaction_trends(manager):
    """GlobeNewswire × Market Reaction（株価/出来高）APIエンドポイント（US向け）"""
    try:
        limit = int(request.args.get('limit', 15))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'GlobeNewswire × Market', 'globenewswire_market_reaction')
        
    except Exception as e:
        return handle_api_error('GlobeNewswire × Market Reaction', e)


@trend_bp.route('/wikipedia-trends')
@require_manager('wikipedia')
def get_wikipedia_trends(manager):
    """Wikipedia 人気記事（Most read）APIエンドポイント。lang=ja（日本）/ en（英語）"""
    try:
        lang = request.args.get('lang', 'ja').lower()
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(lang=lang, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Wikipedia 人気記事', 'Wikipedia Featured API', lang=lang)
        
    except Exception as e:
        return handle_api_error('Wikipedia 人気記事', e)


@trend_bp.route('/producthunt-trends')
@require_manager('producthunt')
def get_producthunt_trends(manager):
    """Product Hunt Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        sort = request.args.get('sort', 'votes')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, sort=sort, force_refresh=force_refresh)
        return handle_trend_response(result, 'Product Huntトレンド', 'Product Hunt API', sort=sort)
        
    except Exception as e:
        return handle_api_error('Product Huntトレンド', e)

@trend_bp.route('/cnn-trends')
@require_manager('cnn')
def get_cnn_trends(manager):
    """CNN ニュース APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'CNNニュース', 'CNN RSS')
        
    except Exception as e:
        return handle_api_error('CNNニュース', e)


@trend_bp.route('/stock-trends')
@require_manager('stock')
def get_stock_trends(manager):
    """Stock Trends APIエンドポイント"""
    try:
        market = request.args.get('market', 'US').upper()  # JP or US
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(market=market, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Stock Trends', 'yfinance', market=market)
        
    except Exception as e:
        return handle_api_error('Stock Trends', e)


@trend_bp.route('/crypto-trends')
@require_manager('crypto')
def get_crypto_trends(manager):
    """Crypto Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Crypto Trends', 'CoinGecko API')
        
    except Exception as e:
        return handle_api_error('Crypto Trends', e)


@trend_bp.route('/movie-trends')
@require_manager('movie')
def get_movie_trends(manager):
    """Movie Trends APIエンドポイント"""
    try:
        country = request.args.get('country', 'JP')  # 'JP' or 'US'
        time_window = request.args.get('time_window', 'day')  # 'day' or 'week'
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(country=country, time_window=time_window, limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Movie Trends', 'TMDB API', time_window=time_window, country=country)
        
    except Exception as e:
        return handle_api_error('Movie Trends', e)


@trend_bp.route('/book-trends')
@require_manager('book')
def get_book_trends(manager):
    """Book Trends APIエンドポイント（5択カテゴリ対応）"""
    try:
        country = request.args.get('country', 'JP').upper()
        category = request.args.get('category', 'all').lower().strip() or 'all'
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        result = manager.get_trends(country=country, limit=limit, force_refresh=force_refresh, category=category)
        source = '楽天ブックスAPI' if country == 'JP' else 'Google Books API'
        return handle_trend_response(result, 'Book Trends', source, country=country, category=category)
    except Exception as e:
        return handle_api_error('Book Trends', e)

@trend_bp.route('/cisa-kev-trends')
@require_manager('cisa_kev')
def get_cisa_kev_trends(manager):
    """CISA KEV Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'CISA KEV', 'CISA KEV API')
        
    except Exception as e:
        return handle_api_error('CISA KEV Trends', e)


@trend_bp.route('/admin-trends')
def get_admin_trends():
    """
    行政データ統合API（e-Stat ＋ 政府調達）
    通常時はキャッシュ優先。再取得ボタン（force_refresh=true）のときは両方の外部APIを呼ぶ。
    """
    managers = get_managers()
    estat_mgr = managers.get('estat')
    kkj_mgr = managers.get('kkj')
    force_refresh = get_force_refresh()

    # e-Stat（完全失業率・実質賃金指数・小売販売額など6指標）
    estat_result = {"success": False, "data": [], "error": "e-Stat Managerが初期化されていません"}
    if estat_mgr:
        try:
            if force_refresh:
                estat_result = estat_mgr.get_trends(limit=6, force_refresh=True)
            else:
                # 初期表示はキャッシュのみ（外部APIを呼ばない）
                estat_result = estat_mgr.get_trends(limit=6, cache_only=True, auto_fetch_on_cache_miss=False)
        except Exception as e:
            logger.exception("e-Stat取得エラー: %s", e)
            estat_result = {"success": False, "data": [], "error": str(e)}
    kkj_result = {"success": False, "data": None, "error": "政府調達 Managerが初期化されていません"}
    if kkj_mgr:
        try:
            if force_refresh:
                # 再取得時は政府調達APIを呼ぶ
                kkj_result = kkj_mgr.get_public_sector_signals(force_refresh=True, cache_only=False)
            else:
                # 初期表示はキャッシュのみ（外部APIを呼ばない）
                kkj_result = kkj_mgr.get_public_sector_signals(cache_only=True)
        except Exception as e:
            logger.exception("政府調達取得エラー: %s", e)
            kkj_result = {"success": False, "data": None, "error": str(e)}
    return jsonify({
        "success": estat_result.get("success", False) or kkj_result.get("success", False),
        "estat": estat_result,
        "kkj": kkj_result,
    })


@trend_bp.route('/estat-trends')
@require_manager('estat')
def get_estat_trends(manager):
    """e-Stat（CPI・有効求人倍率・住宅着工・完全失業率・実質賃金指数・小売業販売額）APIエンドポイント"""
    try:
        force_refresh = get_force_refresh()
        result = manager.get_trends(limit=6, force_refresh=force_refresh)
        return handle_trend_response(result, 'e-Stat', 'e-Stat API')
    except Exception as e:
        return handle_api_error('e-Stat Trends', e)


@trend_bp.route('/us-admin-trends')
def get_us_admin_trends():
    """
    US行政データ統合API（BLS景気指標 ＋ USAspending政府支出）
    1タブで US景気（上）＋ US政府支出（下）を返す。
    """
    managers = get_managers()
    bls_mgr = managers.get('bls')
    usaspending_mgr = managers.get('usaspending')
    force_refresh = get_force_refresh()

    bls_result = {"success": False, "data": [], "error": "BLS Managerが初期化されていません"}
    if bls_mgr:
        try:
            bls_result = bls_mgr.get_trends(limit=10, force_refresh=force_refresh)
        except Exception as e:
            logger.exception("BLS取得エラー: %s", e)
            bls_result = {"success": False, "data": [], "error": str(e)}

    usaspending_result = {"success": False, "data": None, "error": "USAspending Managerが初期化されていません"}
    if usaspending_mgr:
        try:
            usaspending_result = usaspending_mgr.get_trends(force_refresh=force_refresh)
        except Exception as e:
            logger.exception("USAspending取得エラー: %s", e)
            usaspending_result = {"success": False, "data": None, "error": str(e)}

    return jsonify({
        "success": bls_result.get("success", False) or usaspending_result.get("success", False),
        "bls": bls_result,
        "usaspending": usaspending_result,
    })


@trend_bp.route('/kkj-trends')
@require_manager('kkj')
def get_kkj_trends(manager):
    """政府調達 Public Sector Signals（直近30日×AI/DX/サイバー件数＋都道府県ランキング）APIエンドポイント"""
    try:
        force_refresh = get_force_refresh()
        result = manager.get_public_sector_signals(force_refresh=force_refresh)
        return jsonify(result)
    except Exception as e:
        return handle_api_error('政府調達 KKJ Trends', e)


@trend_bp.route('/thehackernews-trends')
@require_manager('thehackernews')
def get_thehackernews_trends(manager):
    """The Hacker News Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'The Hacker News', 'The Hacker News RSS')
        
    except Exception as e:
        return handle_api_error('The Hacker News Trends', e)

@trend_bp.route('/ipa-trends')
@require_manager('ipa')
def get_ipa_trends(manager):
    """IPA注意喚起 Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'IPA注意喚起', 'IPA RSS')
        
    except Exception as e:
        return handle_api_error('IPA Trends', e)

@trend_bp.route('/jpcert-trends')
@require_manager('jpcert')
def get_jpcert_trends(manager):
    """JPCERT/CC Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'JPCERT/CC', 'JPCERT/CC RSS')
        
    except Exception as e:
        return handle_api_error('JPCERT/CC Trends', e)

@trend_bp.route('/hackernoon-trends')
@require_manager('hackernoon')
def get_hackernoon_trends(manager):
    """Hacker Noon Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Hacker Noon', 'Hacker Noon RSS')
        
    except Exception as e:
        return handle_api_error('Hacker Noon Trends', e)

@trend_bp.route('/zenn-trends')
@require_manager('zenn')
def get_zenn_trends(manager):
    """Zenn Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Zenn', 'Zenn RSS')
        
    except Exception as e:
        return handle_api_error('Zenn Trends', e)

@trend_bp.route('/note-trends')
@require_manager('note')
def get_note_trends(manager):
    """Note Trends APIエンドポイント（カテゴリ対応）"""
    try:
        limit = int(request.args.get('limit', 25))
        category = request.args.get('category', 'all')
        force_refresh = get_force_refresh()
        fetch_all_categories = request.args.get('fetch_all_categories', 'false').lower() == 'true'
        
        result = manager.get_trends(
            category=category,
            limit=limit,
            force_refresh=force_refresh,
            fetch_all_categories=fetch_all_categories
        )
        return handle_trend_response(result, 'Note', 'Note RSS')
        
    except Exception as e:
        return handle_api_error('Note Trends', e)

@trend_bp.route('/ebay-trends')
@require_manager('ebay')
def get_ebay_trends(manager):
    """eBay Popular/Trending Trends APIエンドポイント（カテゴリ対応）"""
    try:
        category = request.args.get('category', 'fashion')
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(category=category, limit=limit, force_refresh=force_refresh)
        
        # category情報をレスポンスに含める
        if isinstance(result, dict):
            result['category'] = category
            if 'available_categories' not in result:
                result['available_categories'] = manager.get_available_categories()
        
        return handle_trend_response(result, 'eBay Popular/Trending', 'eBay API', category=category)
        
    except Exception as e:
        return handle_api_error('eBay Popular/Trending Trends', e)

@trend_bp.route('/medium-trends')
@require_manager('medium')
def get_medium_trends(manager):
    """Medium Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'Medium', 'Medium RSS')
        
    except Exception as e:
        return handle_api_error('Medium Trends', e)

@trend_bp.route('/devto-trends')
@require_manager('devto')
def get_devto_trends(manager):
    """DEV.to Trends APIエンドポイント"""
    try:
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(limit=limit, force_refresh=force_refresh)
        return handle_trend_response(result, 'DEV.to', 'DEV.to API')
        
    except Exception as e:
        return handle_api_error('DEV.to Trends', e)
