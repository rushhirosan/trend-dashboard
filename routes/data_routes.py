"""
データ関連のルート
キャッシュデータ、統計情報などのAPIエンドポイント
"""

from flask import Blueprint, jsonify, request
from database_config import TrendsCache

# Blueprintを作成
data_bp = Blueprint('data', __name__, url_prefix='/api')

# キャッシュシステムのインスタンス
cache = TrendsCache()


@data_bp.route('/cache/data-freshness')
def get_data_freshness():
    """データ更新情報タブ用の統一的キャッシュ情報を取得"""
    try:
        freshness_info = {}
        
        # 各カテゴリのキャッシュ情報を取得
        categories = [
            ('google_trends', 'Google Trends'),
            ('youtube_trends', 'YouTube'),
            ('music_trends', 'Spotify'),
            ('worldnews_trends', 'World News'),
            ('podcast_trends', 'Podcast'),
            ('rakuten_trends', '楽天'),
            ('hatena_trends', 'はてなブックマーク'),
            ('twitch_trends', 'Twitch')
        ]
        
        for cache_key, display_name in categories:
            try:
                cache_info = cache.get_cache_info(cache_key)
                if cache_info:
                    freshness_info[display_name] = {
                        'last_updated': cache_info.get('last_updated'),
                        'data_count': cache_info.get('data_count'),
                        'status': '取得済み'
                    }
                else:
                    freshness_info[display_name] = {
                        'last_updated': None,
                        'data_count': 0,
                        'status': 'データなし'
                    }
            except Exception as e:
                freshness_info[display_name] = {
                    'last_updated': None,
                    'data_count': 0,
                    'status': f'エラー: {str(e)}'
                }
        
        return jsonify({
            'success': True,
            'data': freshness_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@data_bp.route('/cache/clear')
def clear_cache():
    """キャッシュをクリア"""
    try:
        cache_type = request.args.get('type', 'all')
        
        if cache_type == 'all':
            # 全キャッシュをクリア
            cache.clear_all_cache()
            message = "全キャッシュをクリアしました"
        else:
            # 特定のキャッシュをクリア
            cache.clear_cache_by_type(cache_type)
            message = f"{cache_type}キャッシュをクリアしました"
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'キャッシュクリアに失敗しました: {str(e)}'
        }), 500


@data_bp.route('/cache/status')
def get_cache_status():
    """キャッシュの状態を取得"""
    try:
        cache_type = request.args.get('type', 'all')
        
        if cache_type == 'all':
            # 全キャッシュの状態を取得
            status = cache.get_all_cache_status()
        else:
            # 特定のキャッシュの状態を取得
            status = cache.get_cache_status(cache_type)
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'キャッシュ状態取得に失敗しました: {str(e)}'
        }), 500


@data_bp.route('/statistics')
def get_statistics():
    """統計情報を取得"""
    try:
        stats = {
            'total_categories': 8,
            'cache_status': cache.get_all_cache_status(),
            'last_updated': cache.get_last_update_time()
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'統計情報取得に失敗しました: {str(e)}'
        }), 500

