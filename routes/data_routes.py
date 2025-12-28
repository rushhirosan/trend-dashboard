"""
データ関連のルート
キャッシュデータ、統計情報などのAPIエンドポイント
"""

import os
from flask import Blueprint, jsonify, request, current_app
from database_config import TrendsCache
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

# Blueprintを作成
data_bp = Blueprint('data', __name__, url_prefix='/api')

# キャッシュシステムのインスタンス（遅延初期化）
_cache_instance = None

def get_cache():
    """キャッシュインスタンスを取得（遅延初期化）"""
    global _cache_instance
    if _cache_instance is None:
        try:
            _cache_instance = TrendsCache()
            logger.info("✅ キャッシュシステムを初期化しました（遅延初期化）")
        except Exception as e:
            logger.error(f"❌ キャッシュシステム初期化エラー: {e}", exc_info=True)
            _cache_instance = None
            logger.warning("⚠️ キャッシュシステムの初期化に失敗しました")
    return _cache_instance


def handle_data_error(operation_name, error, status_code=500):
    """
    データAPIエラーを統一フォーマットで処理
    
    Args:
        operation_name: 操作名
        error: エラーオブジェクト
        status_code: HTTPステータスコード
    """
    logger.error(f"❌ {operation_name} エラー: {error}", exc_info=True)
    return jsonify({
        'success': False,
        'error': f'{operation_name}に失敗しました: {str(error)}'
    }), status_code


@data_bp.route('/cache/data-freshness')
def get_data_freshness():
    """データ更新情報タブ用の統一的キャッシュ情報を取得"""
    try:
        # 国コードを取得（デフォルトはJP）
        country = request.args.get('country', 'JP').upper()
        
        freshness_info = {}
        
        # 各カテゴリのキャッシュ情報を取得
        categories = [
            ('google_trends', 'Google Trends'),
            ('youtube_trends', 'YouTube'),
            ('music_trends', 'Spotify'),
            ('worldnews_trends', 'World News'),
            ('podcast_trends', 'Podcast'),
            ('movie_trends', '映画トレンド'),
            ('book_trends', '本トレンド'),
            ('rakuten_trends', '楽天'),
            ('hatena_trends', 'はてなブックマーク'),
            ('twitch_trends', 'Twitch'),
            ('nhk_trends', 'NHK ニュース'),
            ('qiita_trends', 'Qiita トレンド'),
            ('stock_trends', '株価トレンド'),
            ('crypto_trends', '仮想通貨トレンド'),
            ('cnn_trends', 'CNN News'),
            ('producthunt_trends', 'Product Hunt'),
            ('reddit_trends', 'Reddit'),
            ('hackernews_trends', 'Hacker News')
        ]
        
        cache_instance = get_cache()
        if not cache_instance:
            return jsonify({
                'success': False,
                'error': 'キャッシュシステムが初期化されていません'
            }), 500
        
        for cache_key, display_name in categories:
            try:
                # 映画と本トレンドは国別のキャッシュキーを使用
                if cache_key == 'movie_trends':
                    # 指定された国の映画トレンドを取得
                    cache_info = cache_instance.get_cache_info(f'movie_trends_{country}')
                    if not cache_info:
                        # フォールバック: もう一方の国のデータをチェック
                        fallback_country = 'US' if country == 'JP' else 'JP'
                        cache_info = cache_instance.get_cache_info(f'movie_trends_{fallback_country}')
                elif cache_key == 'book_trends':
                    # 指定された国の本トレンドを取得
                    cache_info = cache_instance.get_cache_info(f'book_trends_{country}')
                    if not cache_info:
                        # フォールバック: もう一方の国のデータをチェック
                        fallback_country = 'US' if country == 'JP' else 'JP'
                        cache_info = cache_instance.get_cache_info(f'book_trends_{fallback_country}')
                else:
                    cache_info = cache_instance.get_cache_info(cache_key)
                
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
        
        cache_instance = get_cache()
        if not cache_instance:
            return jsonify({
                'success': False,
                'error': 'キャッシュシステムが初期化されていません'
            }), 500
        
        if cache_type == 'all':
            # 全キャッシュをクリア
            cache_instance.clear_all_cache()
            message = "全キャッシュをクリアしました"
        else:
            # 特定のキャッシュをクリア
            cache_instance.clear_cache_by_type(cache_type)
            message = f"{cache_type}キャッシュをクリアしました"
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return handle_data_error('キャッシュクリア', e)


@data_bp.route('/cache/status')
def get_cache_status():
    """キャッシュの状態を取得"""
    try:
        cache_type = request.args.get('type', 'all')
        
        cache_instance = get_cache()
        if not cache_instance:
            return jsonify({
                'success': False,
                'error': 'キャッシュシステムが初期化されていません'
            }), 500
        
        if cache_type == 'all':
            # 全キャッシュの状態を取得
            status = cache_instance.get_all_cache_status()
        else:
            # 特定のキャッシュの状態を取得
            status = cache_instance.get_cache_status(cache_type)
        
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
        cache_instance = get_cache()
        if not cache_instance:
            return jsonify({
                'success': False,
                'error': 'キャッシュシステムが初期化されていません'
            }), 500
        
        stats = {
            'total_categories': 8,
            'cache_status': cache_instance.get_all_cache_status() if cache_instance else {},
            'last_updated': cache_instance.get_last_update_time() if cache_instance else None
        }
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return handle_data_error('統計情報取得', e)


@data_bp.route('/cache/refresh-all', methods=['POST'])
def refresh_all_trends_endpoint():
    """すべてのトレンドデータを強制更新"""
    try:
        managers = current_app.config.get('TREND_MANAGERS')
        if not managers:
            return jsonify({
                'success': False,
                'error': 'トレンドマネージャーが初期化されていません'
            }), 500
        
        force_refresh = request.args.get('force_refresh', 'true').lower() == 'true'
        from managers.trend_managers import refresh_all_trends
        result = refresh_all_trends(managers, force_refresh=force_refresh)
        
        # データ更新完了後、メール自動送信を実行
        # ただし、環境変数SKIP_EMAIL_ON_UPDATE=trueの場合はスキップ（デプロイ時の不要なメール送信を防ぐ）
        skip_email = os.getenv('SKIP_EMAIL_ON_UPDATE', 'false').lower() == 'true'
        if not skip_email:
            try:
                from services.subscription.subscription_manager import SubscriptionManager
                subscription_manager = SubscriptionManager()
                subscription_manager.send_trends_summary()
            except Exception as e:
                # メール送信エラーはデータ更新処理を止めないように、ログのみ出力
                logger.warning(f"⚠️ データ更新後のメール自動送信エラー（データ更新は成功）: {e}", exc_info=True)
        else:
            logger.info("⏭️ メール自動送信をスキップします（SKIP_EMAIL_ON_UPDATE=true）")
        
        status_code = 200 if result.get('success') else 207
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'全カテゴリー更新に失敗しました: {str(e)}'
        }), 500


@data_bp.route('/scheduler/execute', methods=['POST'])
def execute_scheduler():
    """スケジューラーを手動実行（メール自動送信を含む）"""
    try:
        scheduler = current_app.config.get('SCHEDULER')
        if not scheduler:
            return jsonify({
                'success': False,
                'error': 'スケジューラーが初期化されていません'
            }), 500
        
        # スケジューラーの_fetch_all_trendsを実行（手動実行のためforce=True）
        # force=Trueの場合、メール送信はスキップされる（明示的な手動実行のため）
        scheduler._fetch_all_trends(force=True)
        
        return jsonify({
            'success': True,
            'message': 'スケジューラー実行完了（データ更新のみ、メール送信はスキップ）'
        })
    except Exception as e:
        return handle_data_error('スケジューラー実行', e)

