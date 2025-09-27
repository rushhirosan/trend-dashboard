"""
トレンド関連のルート
各トレンドカテゴリのAPIエンドポイント
"""

from flask import Blueprint, jsonify, request
from managers.trend_managers import initialize_managers

# Blueprintを作成
trend_bp = Blueprint('trends', __name__, url_prefix='/api')

# マネージャーを初期化
managers = initialize_managers()


@trend_bp.route('/google-trends')
def get_google_trends():
    """Google Trends APIエンドポイント"""
    try:
        # パラメータ取得
        country = request.args.get('country', 'JP')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        # Google Trends Managerを使用
        google_manager = managers.get('google')
        if not google_manager:
            return jsonify({
                'success': False,
                'error': 'Google Trends Managerが初期化されていません'
            })
        
        result = google_manager.get_trends(country, force_refresh=force_refresh)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'country': result.get('country', country),
            'source': result.get('source', 'Google Trends')
        })
        
    except Exception as e:
        print(f"❌ Google Trends API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'Google Trendsの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/youtube-trends')
def get_youtube_trends():
    """YouTube Trends APIエンドポイント"""
    try:
        region = request.args.get('region', 'JP')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['youtube']:
            return jsonify({
                'success': False,
                'error': 'YouTube Managerが初期化されていません'
            }), 500
        
        result = managers['youtube'].get_trends(region, force_refresh=force_refresh)
        
        if isinstance(result, list):
            return jsonify({
                'success': True,
                'data': result,
                'status': 'fresh',
                'region_code': region
            })
        elif isinstance(result, dict) and 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        else:
            return jsonify({
                'success': True,
                'data': result.get('data', []),
                'status': result.get('status', 'unknown'),
                'region_code': result.get('region_code', region)
            })
        
    except Exception as e:
        print(f"❌ YouTube API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'YouTube Trendsの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/music-trends')
def get_music_trends():
    """音楽トレンド APIエンドポイント"""
    try:
        service = request.args.get('service', 'spotify')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['music']:
            return jsonify({
                'success': False,
                'error': 'Music Managerが初期化されていません'
            }), 500
        
        result = managers['music'].get_trends(service, force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'service': service,
            'source': result.get('source', 'Music API')
        })
        
    except Exception as e:
        print(f"❌ Music API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'音楽トレンドの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/news-trends')
def get_news_trends():
    """ニューストレンド APIエンドポイント"""
    try:
        country = request.args.get('country', 'jp')
        category = request.args.get('category', 'general')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['news']:
            return jsonify({
                'success': False,
                'error': 'News Managerが初期化されていません'
            }), 500
        
        result = managers['news'].get_trends(country, category, force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'country': result.get('country', country),
            'category': result.get('category', category),
            'source': result.get('source', 'News API')
        })
        
    except Exception as e:
        print(f"❌ News API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'ニューストレンドの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/worldnews-trends')
def get_worldnews_trends():
    """World News APIエンドポイント"""
    try:
        country = request.args.get('country', 'jp')
        category = request.args.get('category', 'general')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['worldnews']:
            return jsonify({
                'success': False,
                'error': 'World News Managerが初期化されていません'
            }), 500
        
        result = managers['worldnews'].get_trends(country, category, force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'country': result.get('country', country),
            'category': result.get('category', category),
            'source': result.get('source', 'World News API')
        })
        
    except Exception as e:
        print(f"❌ World News API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'World Newsの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/podcast-trends')
def get_podcast_trends():
    """ポッドキャストトレンド APIエンドポイント"""
    try:
        trend_type = request.args.get('trend_type', 'best_podcasts')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['podcast']:
            return jsonify({
                'success': False,
                'error': 'Podcast Managerが初期化されていません'
            }), 500
        
        result = managers['podcast'].get_trends(trend_type, force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'trend_type': trend_type,
            'source': result.get('source', 'Podcast API')
        })
        
    except Exception as e:
        print(f"❌ Podcast API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'ポッドキャストトレンドの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/rakuten-trends')
def get_rakuten_trends():
    """楽天トレンド APIエンドポイント"""
    try:
        genre_id = request.args.get('genre_id', '101070')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['rakuten']:
            return jsonify({
                'success': False,
                'error': 'Rakuten Managerが初期化されていません'
            }), 500
        
        result = managers['rakuten'].get_trends(genre_id, force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'genre_id': genre_id,
            'source': result.get('source', 'Rakuten API')
        })
        
    except Exception as e:
        print(f"❌ Rakuten API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'楽天トレンドの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/hatena-trends')
def get_hatena_trends():
    """はてなブックマークトレンド APIエンドポイント"""
    try:
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['hatena']:
            return jsonify({
                'success': False,
                'error': 'Hatena Managerが初期化されていません'
            }), 500
        
        result = managers['hatena'].get_trends(force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'source': result.get('source', 'Hatena API')
        })
        
    except Exception as e:
        print(f"❌ Hatena API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'はてなブックマークトレンドの取得に失敗しました: {str(e)}'
        }), 500


@trend_bp.route('/twitch-trends')
def get_twitch_trends():
    """Twitchトレンド APIエンドポイント"""
    try:
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not managers['twitch']:
            return jsonify({
                'success': False,
                'error': 'Twitch Managerが初期化されていません'
            }), 500
        
        result = managers['twitch'].get_trends(force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'data': result.get('data', []),
            'status': result.get('status', 'unknown'),
            'source': result.get('source', 'Twitch API')
        })
        
    except Exception as e:
        print(f"❌ Twitch API エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'Twitchトレンドの取得に失敗しました: {str(e)}'
        }), 500
