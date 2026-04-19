"""
WSGI entry point for gunicorn
このファイルはgunicornから直接呼び出されるため、エラーが発生しても必ずappオブジェクトを返す必要があります
"""
import sys
import traceback
from flask import Flask, jsonify

# まず最小限のFlaskアプリを作成（フォールバック用）
fallback_app = Flask(__name__)

@fallback_app.route('/health')
def health_fallback():
    return jsonify({
        'status': 'error',
        'error': 'Application failed to initialize',
        'message': 'Check logs for details'
    }), 200  # 200を返してアプリが動作していることを示す


@fallback_app.route('/healthz')
def healthz_fallback():
    """Fly.io ヘルスチェック用（フォールバック時も 200 を返してポート応答を維持）"""
    return jsonify({
        'status': 'degraded',
        'error': 'Application failed to initialize',
        'message': 'Check logs for details'
    }), 200


@fallback_app.route('/')
def index_fallback():
    return jsonify({
        'error': 'Application initialization failed',
        'message': 'Check logs for details'
    }), 503

# ロガーの初期化を試みる（失敗しても続行）
try:
    from utils.logger_config import get_logger
    logger = get_logger(__name__)
    logger.info("🚀 WSGI初期化開始")
except Exception as e:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.error(f"❌ ロガー初期化エラー: {e}")
    logger.warning("⚠️ デフォルトロガーを使用します")

# アプリケーションとスケジューラーを作成（インポートエラーも含めてすべてのエラーをキャッチ）
app = None
scheduler = None
init_error = None

try:
    # appモジュールのインポートを試みる
    try:
        from app import create_app
        logger.info("✅ appモジュールのインポート成功")
    except ImportError as import_error:
        logger.error(f"❌ appモジュールのインポートエラー: {import_error}", exc_info=True)
        logger.error(f"❌ インポートエラーの詳細:\n{traceback.format_exc()}")
        init_error = import_error
        app = fallback_app
    except Exception as import_error:
        logger.error(f"❌ appモジュールのインポート時の予期しないエラー: {import_error}", exc_info=True)
        logger.error(f"❌ エラーの詳細:\n{traceback.format_exc()}")
        init_error = import_error
        app = fallback_app
    
    # create_app()の呼び出しを試みる
    if app is None:
        try:
            app, scheduler = create_app()
            logger.info("✅ アプリケーション初期化完了")
        except Exception as create_error:
            logger.error(f"❌ アプリケーション初期化エラー: {create_error}", exc_info=True)
            logger.error(f"❌ 初期化エラーの詳細:\n{traceback.format_exc()}")
            init_error = create_error
            app = fallback_app
            scheduler = None
            logger.warning("⚠️ エラーモードでアプリケーションを起動します")
except Exception as e:
    logger.error(f"❌ 予期しないエラー: {e}", exc_info=True)
    logger.error(f"❌ エラーの詳細:\n{traceback.format_exc()}")
    init_error = e
    app = fallback_app
    scheduler = None

# アプリが確実に存在することを確認（Noneの場合はフォールバックアプリを使用）
if app is None:
    logger.error("❌ アプリケーションがNoneです。フォールバックアプリを使用します")
    app = fallback_app

# スケジューラーを開始（各workerでstartするが、ジョブ実行はファイルロックで1プロセスのみ）
# 詳細なログはscheduler_manager.pyで出力されるため、ここでは簡潔に記録
if scheduler:
    try:
        scheduler.start()
        logger.debug("✅ スケジューラー開始（詳細ログはscheduler_managerを参照）")
    except Exception as e:
        logger.warning(f"⚠️ スケジューラー開始エラー: {e}", exc_info=True)
        scheduler = None
        logger.warning("⚠️ スケジューラーは無効です（エラーのため）")
else:
    logger.info("ℹ️ スケジューラーは無効です（初期化されていないか、無効化されています）")

# メモリ逼迫時の Discord 事前警告（OOM 直後はプロセスが死ぬためアプリ内では検知不可）
try:
    from utils.memory_watchdog import start_memory_watchdog

    start_memory_watchdog()
except Exception as mw_err:
    logger.warning("⚠️ memory_watchdog 開始スキップ: %s", mw_err)

# 最終確認：appが確実に存在し、Flaskアプリケーションであることを確認
if not isinstance(app, Flask):
    logger.error(f"❌ アプリケーションがFlaskインスタンスではありません（型: {type(app)}）。フォールバックアプリを使用します")
    app = fallback_app

# アプリが確実に0.0.0.0:8080でリッスンできることを確認するためのログ
# 最終確認とログ出力
logger.info("=" * 60)
logger.info("✅ WSGI初期化完了 - アプリケーションは起動可能な状態です")
logger.info(f"✅ アプリケーション型: {type(app)}")
logger.info(f"✅ アプリケーション名: {app.name if hasattr(app, 'name') else 'unknown'}")
logger.info("✅ gunicornが0.0.0.0:8080でリッスンします")
if init_error:
    logger.warning(f"⚠️ 初期化エラーが発生しましたが、アプリは起動します: {init_error}")
logger.info("=" * 60)

