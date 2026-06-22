"""
データ関連のルート
キャッシュデータ、統計情報などのAPIエンドポイント
"""

import os
from datetime import date
from flask import Blueprint, jsonify, request, current_app
from database_config import TrendsCache
from utils.cache_status_keys import freshness_lookup_keys
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
    """データ更新情報タブ用の統一的キャッシュ情報を取得（最適化版：1回のクエリで全データ取得）"""
    try:
        # 国コードを取得（デフォルトはJP）
        country = request.args.get('country', 'JP').upper()
        
        cache_instance = get_cache()
        if not cache_instance:
            return jsonify({
                'success': False,
                'error': 'キャッシュシステムが初期化されていません'
            }), 500
        
        # 1回のクエリで全キャッシュ情報を取得（最適化）
        all_cache_status = cache_instance.get_all_cache_status()
        
        # カテゴリマッピング（cache_key -> display_name）
        cache_key_map = {
            'google_trends': 'Google Trends',
            'youtube_trends': 'YouTube',
            'music_trends': 'Apple Music',
            'worldnews_trends': 'World News',
            'podcast_trends': 'Podcast',
            'movie_trends': '映画トレンド',
            'book_trends': '本トレンド',
            'rakuten_trends': '楽天',
            'hatena_trends': 'はてなブックマーク',
            'twitch_trends': 'Twitch',
            'openalex_trends_trending': 'OpenAlex',
            'bluesky_trends': 'Bluesky',
            'nhk_trends': 'NHK ニュース',
            'qiita_trends': 'Qiita トレンド',
            'stock_trends': '株価トレンド',
            'crypto_trends': '仮想通貨トレンド',
            'cnn_trends': 'CNN News',
            'producthunt_trends': 'Product Hunt',
            'hackernews_trends': 'Hacker News',
            'github_trends': 'GitHub',
            'appstore_trends': 'App Store',
            'estat_trends': 'e-Stat',
            'kkj_trends': '政府調達',
            'bls_trends': 'BLS',
            'usaspending_trends': 'USAspending',
            # 新しく追加されたセキュリティトレンド
            'ipa_trends': 'IPA',
            'jpcert_trends': 'JPCERT/CC',
            'cisa_kev_trends': 'CISA KEV',
            'thehackernews_trends': 'The Hacker News',
            'hackernoon_trends': 'Hacker Noon',
            # 新しく追加されたトレンド
            'zenn_trends': 'Zenn',
            'note_trends_all': 'Note (総合)',
            'note_trends_tech': 'Note (テクノロジー)',
            'note_trends_business': 'Note (ビジネス)',
            'note_trends_lifestyle': 'Note (ライフスタイル)',
            'note_trends_entertainment': 'Note (エンタメ)',
            'ebay_trends': 'eBay Popular/Trending',
            'devto_trends': 'DEV.to',
            'medium_trends': 'Medium',
            'wikipedia_trends_ja': 'Wikipedia 人気記事 (日本語)',
            'wikipedia_trends_en': 'Wikipedia 人気記事 (英語)',
            # 日本: プレスリリーストレンド
            'prtimes_hatena_trends': 'PR TIMES × はてブ',
            # US: プレスリリーストレンド
            'globenewswire_trends': 'GlobeNewswire',
        }
        
        freshness_info = {}
        
        for cache_key, display_name in cache_key_map.items():
            try:
                cache_info = None
                for lookup_key in freshness_lookup_keys(cache_key, country):
                    cache_info = all_cache_status.get(lookup_key)
                    if cache_info:
                        break
                
                if cache_info:
                    # last_updatedがdatetimeオブジェクトの場合はisoformatに変換
                    last_updated = cache_info.get('last_updated')
                    if last_updated and hasattr(last_updated, 'isoformat'):
                        last_updated = last_updated.isoformat()
                    
                    freshness_info[display_name] = {
                        'last_updated': last_updated,
                        'data_count': cache_info.get('data_count', 0),
                        'status': '取得済み'
                    }
                else:
                    freshness_info[display_name] = {
                        'last_updated': None,
                        'data_count': 0,
                        'status': 'データなし'
                    }
            except Exception as e:
                logger.warning(f"⚠️ {display_name} キャッシュ情報取得エラー: {e}")
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
        logger.error(f"❌ データ鮮度情報取得エラー: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
        logger.info("🔄 /api/cache/refresh-all エンドポイントにリクエストが到達しました")
        managers = current_app.config.get('TREND_MANAGERS')
        if not managers:
            logger.error("❌ トレンドマネージャーが初期化されていません")
            return jsonify({
                'success': False,
                'error': 'トレンドマネージャーが初期化されていません'
            }), 500
        
        force_refresh = request.args.get('force_refresh', 'true').lower() == 'true'
        logger.info(f"🔄 refresh_all_trends実行開始 (force_refresh={force_refresh})")
        from managers.trend_managers import refresh_all_trends
        result = refresh_all_trends(managers, force_refresh=force_refresh)
        logger.info(f"✅ refresh_all_trends実行完了: success={result.get('success')}")
        
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

        slot_key = (request.args.get('slot_key') or '').strip() or None
        low_memory_mode = request.args.get('low_memory', 'true').lower() in ('1', 'true', 'yes')
        run_async = request.args.get('async', 'true').lower() in ('1', 'true', 'yes')

        app_obj = current_app._get_current_object()
        scheduler_ref = scheduler

        def _run_fetch():
            with app_obj.app_context():
                scheduler_ref._fetch_all_trends(
                    force=True,
                    trigger_source='api',
                    low_memory_mode=low_memory_mode,
                    slot_key_override=slot_key,
                )

        # 長時間ジョブは Gunicorn ワーカー内バックグラウンドで実行（fly ssh 二重 create_app を避ける）
        if run_async:
            import threading

            threading.Thread(target=_run_fetch, daemon=True, name='scheduler-manual-fetch').start()
            return jsonify({
                'success': True,
                'message': 'スケジューラー実行を開始しました（バックグラウンド）',
                'slot_key': slot_key,
                'low_memory_mode': low_memory_mode,
            })

        _run_fetch()
        return jsonify({
            'success': True,
            'message': 'スケジューラー実行完了（データ更新のみ、メール送信はスキップ）',
            'slot_key': slot_key,
        })
    except Exception as e:
        return handle_data_error('スケジューラー実行', e)


@data_bp.route('/scheduler/lock-status')
def scheduler_lock_status():
    """スケジューラー分散ロックの現在状態（デバッグ用）。Discordが来ない原因切り分けに利用。"""
    try:
        cache = get_cache()
        if not cache or not hasattr(cache, 'get_scheduler_lock_status'):
            return jsonify({'success': False, 'error': 'キャッシュ/ロック状態を取得できません'}), 500
        status = cache.get_scheduler_lock_status()
        return jsonify({'success': True, 'lock': status})
    except Exception as e:
        return handle_data_error('ロック状態取得', e)


@data_bp.route('/summaries/daily-snapshots')
def get_daily_snapshots_for_ai_summary():
    """business_day ごとの trend_daily_snapshots（スロット 01/07/13/19）を返す。

    GitHub Actions など Fly 外から DB に繋げない環境で、本番アプリ経由で
    ``scripts/generate_ai_daily_summary.py --from-api`` が同じ入力を得るために使う。
    """
    raw = (request.args.get("business_day") or "").strip()
    if not raw:
        return jsonify({"success": False, "error": "business_day query parameter is required"}), 400
    try:
        business_day = date.fromisoformat(raw)
    except ValueError:
        return jsonify({"success": False, "error": "business_day must be YYYY-MM-DD"}), 400

    cache_instance = get_cache()
    if not cache_instance:
        return jsonify({"success": False, "error": "キャッシュシステムが初期化されていません"}), 500

    rows = cache_instance.get_trend_daily_snapshots_for_business_day(business_day)
    # JSON 応答用に dict 化（RealDictRow / datetime をそのまま jsonify できるよう揃える）
    out = []
    for row in rows:
        cap = row.get("captured_at")
        cap_s = cap.isoformat() if hasattr(cap, "isoformat") else str(cap)
        out.append(
            {
                "slot": row.get("slot"),
                "series_key": row.get("series_key"),
                "items": row.get("items"),
                "captured_at": cap_s,
            }
        )
    return jsonify(
        {
            "success": True,
            "business_day": business_day.isoformat(),
            "data": out,
        }
    )


@data_bp.route('/alert/test', methods=['GET', 'POST'])
def test_alert():
    """Discord Webhook の状態確認（GET）とテスト送信（POST）"""
    try:
        from utils.alert_service import AlertService
        from utils.memory_watchdog import get_memory_status

        svc = AlertService()
        webhook_ok = bool(svc.webhook_url)

        if request.method == 'GET':
            return jsonify({
                'success': True,
                'webhook_configured': webhook_ok,
                'memory': get_memory_status(),
                'memory_watchdog': {
                    'enabled_env': os.getenv('DISCORD_MEMORY_PRESSURE_ALERT', 'true'),
                    'hint': 'POST 同じURLでテストメッセージを Discord に送信します',
                },
                'discord_hint': (
                    'webhook_configured=false のとき: fly secrets set DISCORD_WEBHOOK_URL=... で設定し、'
                    'URL に discord が含まれることを確認してください。'
                    if not webhook_ok else None
                ),
            }), 200

        if not svc.webhook_url:
            return jsonify({
                'success': False,
                'error': 'DISCORD_WEBHOOK_URL が未設定か、URL に discord が含まれません。',
                'detail': getattr(svc, 'last_send_error', None),
            }), 400
        ok = svc.send_alert(
            'warning',
            'アラートテスト',
            'Discord アラートのテスト送信です。このメッセージが届いていれば Webhook は正常です。',
            {'環境': 'test', 'エンドポイント': '/api/alert/test'},
        )
        if not ok:
            return jsonify({
                'success': False,
                'error': 'Discord 送信に失敗しました。',
                'detail': getattr(svc, 'last_send_error', None),
            }), 500
        return jsonify({
            'success': True,
            'message': 'Discord にテストアラートを送信しました。チャンネルを確認してください。'
        })
    except Exception as e:
        return handle_data_error('アラートテスト', e)

