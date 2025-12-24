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
    # エラーが含まれている場合（status_codeが指定されている場合はそれを使用）
    if isinstance(result, dict) and 'error' in result:
        error_response = {
            'success': False,
            'error': result['error']
        }
        # 追加情報がある場合は含める
        for key in ['status_code', 'suggestion', 'response_text']:
            if key in result:
                error_response[key] = result[key]
        
        status_code = result.get('status_code', 500)
        return jsonify(error_response), status_code
    
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
            error_response = {
                'success': False,
                'error': result.get('error', 'Unknown error')
            }
            # 追加情報がある場合は含める
            for key in ['status_code', 'suggestion', 'response_text']:
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
                   'subreddit', 'story_type', 'sort', 'service', 'genre_id']:
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

        result = manager.get_trends(country, force_refresh=force_refresh)
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


@trend_bp.route('/news-trends')
@require_manager('news')
def get_news_trends(manager):
    """ニューストレンド APIエンドポイント"""
    try:
        country = request.args.get('country', 'jp')
        category = request.args.get('category', 'general')
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(country, category, force_refresh=force_refresh)
        return handle_trend_response(result, 'ニューストレンド', 'News API',
                                    country=country, category=category)
        
    except Exception as e:
        return handle_api_error('ニューストレンド', e)


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


@trend_bp.route('/rakuten-trends')
@require_manager('rakuten')
def get_rakuten_trends(manager):
    """楽天トレンド APIエンドポイント"""
    try:
        genre_id = request.args.get('genre_id', '101070')
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
    """Book Trends APIエンドポイント"""
    try:
        country = request.args.get('country', 'JP').upper()  # 'JP' or 'US'
        limit = int(request.args.get('limit', 25))
        force_refresh = get_force_refresh()
        
        result = manager.get_trends(country=country, limit=limit, force_refresh=force_refresh)
        source = '楽天ブックスAPI' if country == 'JP' else 'Google Books API'
        return handle_trend_response(result, 'Book Trends', source, country=country)
        
    except Exception as e:
        return handle_api_error('Book Trends', e)
