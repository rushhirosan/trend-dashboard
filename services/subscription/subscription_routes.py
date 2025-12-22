"""
サブスクリプション関連のルート定義
Flask Blueprintを使用してルートを分離
"""

from flask import Blueprint, request, jsonify, render_template
from .subscription_manager import SubscriptionManager
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)

# Blueprintを作成
subscription_bp = Blueprint('subscription', __name__, url_prefix='/subscription')

# サブスクリプション管理クラスのインスタンス
subscription_manager = SubscriptionManager()


@subscription_bp.route('/')
def subscription_page():
    """サブスクリプションページを表示"""
    try:
        from flask import current_app
        # Google Analytics IDをテンプレートに渡す
        ga_id = current_app.config.get('GOOGLE_ANALYTICS_ID')
        return render_template('subscription.html', config={'GOOGLE_ANALYTICS_ID': ga_id})
    except Exception as e:
        logger.error(f"❌ サブスクリプションページ表示エラー: {e}", exc_info=True)
        return jsonify({'error': 'ページの表示に失敗しました'}), 500


@subscription_bp.route('/api/subscribe', methods=['POST'])
def subscribe():
    """サブスクリプション登録API"""
    try:
        data = request.get_json()
        email = data.get('email')
        frequency = data.get('frequency', 'daily')
        categories = data.get('categories')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'メールアドレスが必要です'
            }), 400
        
        # サブスクリプション登録
        success, message = subscription_manager.subscribe(email, frequency, categories)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"❌ サブスクリプション登録APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/unsubscribe', methods=['POST'])
def unsubscribe():
    """サブスクリプション登録解除API"""
    try:
        data = request.get_json()
        email = data.get('email')
        token = data.get('token')
        
        # サブスクリプション登録解除
        success, message = subscription_manager.unsubscribe(email, token)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"❌ サブスクリプション登録解除APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/status')
def subscription_status():
    """サブスクリプション状態確認API"""
    try:
        email = request.args.get('email')
        
        # emailパラメータがない場合は未登録として扱う
        if not email:
            return jsonify({
                'subscribed': False,
                'message': 'メールアドレスが指定されていません'
            })
        
        # サブスクリプション状態を取得
        subscription = subscription_manager.get_subscription_status(email)
        
        if subscription:
            return jsonify({
                'subscribed': True,
                'email': subscription['email'],
                'frequency': subscription['frequency'],
                'categories': subscription['categories'],
                'subscribed_at': subscription['created_at'].isoformat() if subscription['created_at'] else None
            })
        else:
            return jsonify({
                'subscribed': False,
                'message': 'サブスクリプションが見つかりません'
            })
            
    except Exception as e:
        logger.error(f"❌ サブスクリプション状態確認APIエラー: {e}", exc_info=True)
        return jsonify({
            'subscribed': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/list')
def subscription_list():
    """サブスクリプション一覧取得API（管理者用）"""
    try:
        # 全アクティブサブスクリプションを取得
        subscriptions = subscription_manager.get_all_active_subscriptions()
        
        return jsonify({
            'success': True,
            'data': subscriptions,
            'count': len(subscriptions)
        })
        
    except Exception as e:
        logger.error(f"❌ サブスクリプション一覧取得APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/update', methods=['POST'])
def update_subscription():
    """サブスクリプション情報更新API"""
    try:
        data = request.get_json()
        email = data.get('email')
        frequency = data.get('frequency')
        categories = data.get('categories')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'メールアドレスが必要です'
            }), 400
        
        # サブスクリプション情報を更新
        success, message = subscription_manager.update_subscription(email, frequency, categories)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400
            
    except Exception as e:
        logger.error(f"❌ サブスクリプション更新APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/send-trends-summary', methods=['POST'])
def send_trends_summary():
    """トレンドサマリー配信API（管理者用）"""
    try:
        # トレンドサマリー配信を実行
        subscription_manager.send_trends_summary()
        
        return jsonify({
            'success': True,
            'message': 'トレンドサマリー配信を実行しました'
        })
        
    except Exception as e:
        logger.error(f"❌ トレンドサマリー配信APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'トレンドサマリー配信に失敗しました'
        }), 500

@subscription_bp.route('/api/statistics')
def subscription_statistics():
    """サブスクリプション統計情報取得API（管理者用）"""
    try:
        # 統計情報を取得
        stats = subscription_manager.get_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"❌ サブスクリプション統計取得APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/api/frequency/<frequency>')
def get_subscriptions_by_frequency(frequency):
    """指定された配信頻度のサブスクリプション一覧取得API"""
    try:
        if frequency not in ['daily', 'weekly', 'monthly']:
            return jsonify({
                'success': False,
                'error': '無効な配信頻度です'
            }), 400
        
        # 配信頻度別サブスクリプションを取得
        subscriptions = subscription_manager.get_subscriptions_by_frequency(frequency)
        
        return jsonify({
            'success': True,
            'data': subscriptions,
            'count': len(subscriptions),
            'frequency': frequency
        })
        
    except Exception as e:
        logger.error(f"❌ 配信頻度別サブスクリプション取得APIエラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'サーバーエラーが発生しました'
        }), 500


@subscription_bp.route('/unsubscribe/<token>')
def unsubscribe_by_token(token):
    """トークンによる登録解除ページ"""
    try:
        # トークンで登録解除
        success, message = subscription_manager.unsubscribe(token=token)
        
        if success:
            return render_template('unsubscribe_success.html', message=message)
        else:
            return render_template('unsubscribe_error.html', error=message)
            
    except Exception as e:
        logger.error(f"❌ トークン登録解除エラー: {e}", exc_info=True)
        return render_template('unsubscribe_error.html', error='登録解除に失敗しました')

