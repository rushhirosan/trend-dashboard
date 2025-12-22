"""
Trends Dashboard - メインアプリケーション
機能別に分割されたモジュールを使用
"""

import os
from dotenv import load_dotenv
from flask import Flask, render_template

# .envファイルを読み込み
load_dotenv()
from config.app_config import AppConfig
from database_config import TrendsCache
from managers.trend_managers import initialize_managers
from routes.trend_routes import trend_bp
from routes.data_routes import data_bp
from services.subscription.subscription_routes import subscription_bp
from services.scheduler.scheduler_manager import TrendsScheduler
from utils.logger_config import get_logger

# ロガーの初期化
logger = get_logger(__name__)


def create_app():
    """Flaskアプリケーションを作成（エラーが発生しても必ずアプリを返す）"""
    logger.info("🚀 アプリケーション初期化開始")
    
    try:
        app = Flask(__name__)
        logger.info("✅ Flaskアプリケーション作成完了")
    except Exception as e:
        logger.error(f"❌ Flaskアプリケーション作成エラー: {e}", exc_info=True)
        raise  # Flaskアプリ作成に失敗した場合は再スロー
    
    # 設定を適用
    try:
        config = AppConfig.get_config_dict()
        app.config.update(config)
        logger.info("✅ アプリケーション設定適用完了")
    except Exception as e:
        logger.error(f"❌ 設定適用エラー: {e}", exc_info=True)
        # 設定が失敗してもデフォルト設定で続行
        app.config.update({
            'DEBUG': False,
            'HOST': '0.0.0.0',
            'PORT': 8080
        })
        logger.warning("⚠️ デフォルト設定で続行します")
    
    # Blueprintを登録（エラーが発生しても続行）
    try:
        app.register_blueprint(trend_bp)
        logger.info("✅ trend_bp Blueprint登録完了")
    except Exception as e:
        logger.error(f"❌ trend_bp登録エラー: {e}", exc_info=True)
    
    try:
        app.register_blueprint(data_bp)
        logger.info("✅ data_bp Blueprint登録完了")
    except Exception as e:
        logger.error(f"❌ data_bp登録エラー: {e}", exc_info=True)
    
    try:
        app.register_blueprint(subscription_bp)
        logger.info("✅ subscription_bp Blueprint登録完了")
    except Exception as e:
        logger.error(f"❌ subscription_bp登録エラー: {e}", exc_info=True)
    
    # データベースを初期化（接続失敗時は警告のみでアプリは起動を続行）
    cache = None
    try:
        cache = TrendsCache()
        if not cache.connection:
            # 接続を再試行
            try:
                cache.connect()
            except Exception as connect_error:
                logger.error(f"❌ データベース接続エラー: {connect_error}")
                logger.warning("⚠️ データベース接続に失敗しましたが、アプリは起動を続行します（一部機能が制限される可能性があります）")
                cache = None
        
        # データベース接続が成功した場合のみテーブルを作成
        if cache and cache.connection:
            try:
                if not cache.init_database():
                    logger.warning("⚠️ データベーステーブル作成に失敗しましたが、アプリは起動を続行します")
                else:
                    logger.info("✅ データベース初期化完了")
            except Exception as init_error:
                logger.error(f"❌ データベーステーブル作成エラー: {init_error}")
                logger.warning("⚠️ データベーステーブル作成に失敗しましたが、アプリは起動を続行します")
        else:
            logger.warning("⚠️ データベース接続が確立されていません。一部機能が制限される可能性があります")
    except Exception as e:
        logger.error(f"❌ データベース初期化エラー: {e}", exc_info=True)
        logger.warning("⚠️ データベース初期化に失敗しましたが、アプリは起動を続行します（一部機能が制限される可能性があります）")
        cache = None
    
    # cacheをapp.configに保存（healthエンドポイントで使用）
    app.config['TRENDS_CACHE'] = cache
    
    # BigQueryクライアントを初期化（TrendsCacheクラスに統合済み）
    try:
        logger.info("✅ BigQueryクライアント初期化完了（TrendsCacheクラスに統合済み）")
    except Exception as e:
        logger.warning(f"⚠️ BigQueryクライアント初期化警告: {e}")
    
    # マネージャーを初期化（エラーが発生しても続行）
    try:
        app.config['TREND_MANAGERS'] = initialize_managers()
        manager_count = len([m for m in app.config['TREND_MANAGERS'].values() if m is not None])
        logger.info(f"✅ トレンドマネージャー初期化完了（{manager_count}個のマネージャーが初期化されました）")
    except Exception as e:
        logger.error(f"❌ トレンドマネージャー初期化エラー: {e}", exc_info=True)
        app.config['TREND_MANAGERS'] = {}
        logger.warning("⚠️ トレンドマネージャーを空の辞書で初期化しました（一部機能が制限されます）")
    
    # スケジューラーを初期化（環境変数で制御可能、エラーが発生しても続行）
    scheduler = None
    try:
        if config.get('ENABLE_SCHEDULER', True):
            try:
                scheduler = TrendsScheduler(app)
                app.config['SCHEDULER'] = scheduler
                logger.info("✅ スケジューラーを初期化しました")
            except Exception as e:
                logger.error(f"❌ スケジューラー初期化エラー: {e}", exc_info=True)
                scheduler = None
                app.config['SCHEDULER'] = None
                logger.warning("⚠️ スケジューラーは無効です（一部機能が制限されます）")
        else:
            scheduler = None
            app.config['SCHEDULER'] = None
            logger.info("🔄 スケジューラーは無効化されています（ENABLE_SCHEDULER=false）")
    except Exception as e:
        logger.error(f"❌ スケジューラー設定エラー: {e}", exc_info=True)
        scheduler = None
        app.config['SCHEDULER'] = None
    
    # ルートを定義（エラーが発生しても続行）
    # パフォーマンス最適化: キャッシュヘッダーの設定
    @app.after_request
    def set_cache_headers(response):
        """静的ファイルにキャッシュヘッダーを設定"""
        # 静的ファイル（CSS、JS、画像）にキャッシュヘッダーを設定
        if response.content_type and (
            'text/css' in response.content_type or
            'application/javascript' in response.content_type or
            'image/' in response.content_type or
            'font/' in response.content_type
        ):
            # 静的ファイルは1年間キャッシュ（バージョニングで更新）
            response.cache_control.max_age = 31536000  # 1年
            response.cache_control.public = True
            response.cache_control.immutable = True
        # HTMLファイルは短いキャッシュ（5分）
        elif response.content_type and 'text/html' in response.content_type:
            response.cache_control.max_age = 300  # 5分
            response.cache_control.public = True
        return response
    
    try:
        @app.route('/test')
        def test_page():
            """テストページ（デバッグ用）"""
            try:
                return render_template('test.html')
            except Exception as e:
                logger.error(f"❌ テストページレンダリングエラー: {e}")
                return f"Error rendering test page: {e}", 500
    except Exception as e:
        logger.error(f"❌ /test ルート定義エラー: {e}", exc_info=True)
    
    try:
        @app.route('/')
        def index():
            """メインページ"""
            try:
                # Google Analytics IDをテンプレートに渡す
                ga_id = app.config.get('GOOGLE_ANALYTICS_ID')
                return render_template('index.html', config={'GOOGLE_ANALYTICS_ID': ga_id})
            except Exception as e:
                logger.error(f"❌ メインページレンダリングエラー: {e}", exc_info=True)
                return f"Error rendering index page: {e}", 500
    except Exception as e:
        logger.error(f"❌ / ルート定義エラー: {e}", exc_info=True)
    
    try:
        @app.route('/us')
        def us_trends():
            """アメリカトレンドページ"""
            try:
                # Google Analytics IDをテンプレートに渡す
                ga_id = app.config.get('GOOGLE_ANALYTICS_ID')
                return render_template('us_trends.html', config={'GOOGLE_ANALYTICS_ID': ga_id})
            except Exception as e:
                logger.error(f"❌ USトレンドページレンダリングエラー: {e}", exc_info=True)
                return f"Error rendering US trends page: {e}", 500
    except Exception as e:
        logger.error(f"❌ /us ルート定義エラー: {e}", exc_info=True)
    
    try:
        @app.route('/data-status')
        def data_status():
            """データ鮮度情報ページ"""
            try:
                # Google Analytics IDをテンプレートに渡す
                ga_id = app.config.get('GOOGLE_ANALYTICS_ID')
                return render_template('data-status.html', config={'GOOGLE_ANALYTICS_ID': ga_id})
            except Exception as e:
                logger.error(f"❌ データステータスページレンダリングエラー: {e}", exc_info=True)
                return f"Error rendering data status page: {e}", 500
    except Exception as e:
        logger.error(f"❌ /data-status ルート定義エラー: {e}", exc_info=True)
    
    try:
        @app.route('/robots.txt')
        def robots_txt():
            """robots.txtを返す"""
            try:
                from flask import Response
                robots_content = """User-agent: *
Allow: /
Disallow: /api/
Disallow: /health
Sitemap: https://trends-dashboard.fly.dev/sitemap.xml
"""
                return Response(robots_content, mimetype='text/plain')
            except Exception as e:
                logger.error(f"❌ robots.txt生成エラー: {e}")
                return "User-agent: *\nDisallow: /", 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        logger.error(f"❌ /robots.txt ルート定義エラー: {e}", exc_info=True)
    
    try:
        @app.route('/sitemap.xml')
        def sitemap_xml():
            """sitemap.xmlを生成"""
            try:
                from flask import Response
                from datetime import datetime
                import pytz
                
                jst = pytz.timezone('Asia/Tokyo')
                now = datetime.now(jst).strftime('%Y-%m-%d')
                
                sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://trends-dashboard.fly.dev/</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://trends-dashboard.fly.dev/us</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://trends-dashboard.fly.dev/data-status</loc>
    <lastmod>{now}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://trends-dashboard.fly.dev/subscription</loc>
    <lastmod>{now}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
"""
                return Response(sitemap_content, mimetype='application/xml')
            except Exception as e:
                logger.error(f"❌ sitemap.xml生成エラー: {e}", exc_info=True)
                return "<?xml version='1.0' encoding='UTF-8'?><urlset></urlset>", 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        logger.error(f"❌ /sitemap.xml ルート定義エラー: {e}", exc_info=True)
    
    def check_database_health(cache_instance):
        """データベース接続のヘルスチェック"""
        import time
        if not cache_instance:
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': 'Database cache instance not initialized'
            }
        try:
            db_check_start = time.time()
            db_conn = cache_instance.get_connection()
            db_check_time = (time.time() - db_check_start) * 1000  # ミリ秒
            
            if db_conn and not db_conn.closed:
                # 簡単なクエリで接続を確認
                with db_conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                
                return {
                    'status': 'healthy',
                    'connected': True,
                    'response_time_ms': round(db_check_time, 2)
                }
            else:
                return {
                    'status': 'unhealthy',
                    'connected': False,
                    'error': 'Database connection is closed or None'
                }
        except Exception as e:
            logger.warning(f"Health check: Database connection failed: {e}")
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }
    
    def check_managers_health(managers):
        """マネージャー初期化状態のヘルスチェック"""
        manager_status = {}
        manager_count = 0
        healthy_manager_count = 0
        
        for key, manager in managers.items():
            manager_count += 1
            if manager is not None:
                healthy_manager_count += 1
                manager_status[key] = 'initialized'
            else:
                manager_status[key] = 'not_initialized'
        
        return {
            'status': 'healthy' if healthy_manager_count == manager_count else 'degraded',
            'total': manager_count,
            'initialized': healthy_manager_count,
            'details': manager_status
        }, healthy_manager_count == manager_count
    
    def check_cache_health(cache_instance):
        """キャッシュ状態のヘルスチェック"""
        if not cache_instance:
            return {
                'status': 'unhealthy',
                'error': 'Cache instance not initialized'
            }, False
        try:
            cache_status_info = cache_instance.get_all_cache_status()
            if cache_status_info:
                cache_keys = list(cache_status_info.keys())
                # キャッシュの詳細情報を取得
                cache_details = {}
                for key in cache_keys[:5]:  # 最初の5個の詳細を取得
                    info = cache_status_info[key]
                    cache_details[key] = {
                        'last_updated': info.get('last_updated').isoformat() if info.get('last_updated') else None,
                        'data_count': info.get('data_count', 0)
                    }
                
                return {
                    'status': 'healthy',
                    'available_caches': len(cache_keys),
                    'total_cache_keys': cache_keys,
                    'sample_details': cache_details
                }, True
            else:
                return {
                    'status': 'degraded',
                    'available_caches': 0,
                    'message': 'No cache status available'
                }, True
        except Exception as e:
            logger.warning(f"Health check: Cache status check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }, False
    
    def check_scheduler_health(scheduler):
        """スケジューラー状態のヘルスチェック"""
        if not scheduler:
            return {
                'status': 'degraded',
                'initialized': False,
                'message': 'Scheduler not initialized'
            }, True
        
        try:
            # スケジューラーが実行中か確認
            scheduler_running = scheduler.scheduler.running if hasattr(scheduler, 'scheduler') else False
            
            # スケジューラーの詳細情報を取得
            scheduler_details = {
                'status': 'healthy' if scheduler_running else 'degraded',
                'initialized': True,
                'running': scheduler_running
            }
            
            # スケジューラーのジョブ情報を取得
            if hasattr(scheduler, 'get_status'):
                try:
                    scheduler_status = scheduler.get_status()
                    scheduler_details['is_running'] = scheduler_status.get('is_running', False)
                    scheduler_details['jobs'] = scheduler_status.get('jobs', [])
                except Exception as e:
                    logger.warning(f"スケジューラー状態取得エラー: {e}")
            
            return scheduler_details, scheduler_running
        except Exception as e:
            return {
                'status': 'unhealthy',
                'initialized': True,
                'error': str(e)
            }, False
    
    @app.route('/health')
    def health():
        """ヘルスチェック用エンドポイント（詳細情報付き、エラーが発生しても必ずレスポンスを返す）"""
        from flask import jsonify
        from datetime import datetime
        
        try:
            health_status = {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'checks': {}
            }
            
            overall_healthy = True
            
            # 1. DB接続チェック（エラーが発生しても続行）
            try:
                cache_instance = app.config.get('TRENDS_CACHE')
                if cache_instance:
                    db_check_result = check_database_health(cache_instance)
                    health_status['checks']['database'] = db_check_result
                    if db_check_result.get('status') != 'healthy':
                        overall_healthy = False
                else:
                    health_status['checks']['database'] = {
                        'status': 'unhealthy',
                        'connected': False,
                        'error': 'Database cache not initialized'
                    }
                    overall_healthy = False
            except Exception as e:
                logger.error(f"❌ データベースヘルスチェックエラー: {e}", exc_info=True)
                health_status['checks']['database'] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False
            
            # 2. API可用性チェック（マネージャー初期化状態、エラーが発生しても続行）
            try:
                managers = app.config.get('TREND_MANAGERS', {})
                managers_check_result, managers_healthy = check_managers_health(managers)
                health_status['checks']['managers'] = managers_check_result
                if not managers_healthy:
                    overall_healthy = False
            except Exception as e:
                logger.error(f"❌ マネージャーヘルスチェックエラー: {e}", exc_info=True)
                health_status['checks']['managers'] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False
            
            # 3. キャッシュ状態の確認（エラーが発生しても続行）
            try:
                cache_instance = app.config.get('TRENDS_CACHE')
                if cache_instance:
                    cache_check_result, cache_healthy = check_cache_health(cache_instance)
                    health_status['checks']['cache'] = cache_check_result
                    if not cache_healthy:
                        overall_healthy = False
                else:
                    health_status['checks']['cache'] = {
                        'status': 'unhealthy',
                        'error': 'Cache not initialized'
                    }
                    overall_healthy = False
            except Exception as e:
                logger.error(f"❌ キャッシュヘルスチェックエラー: {e}", exc_info=True)
                health_status['checks']['cache'] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False
            
            # 4. スケジューラーの状態（エラーが発生しても続行）
            try:
                scheduler = app.config.get('SCHEDULER')
                scheduler_check_result, scheduler_healthy = check_scheduler_health(scheduler)
                health_status['checks']['scheduler'] = scheduler_check_result
                if not scheduler_healthy:
                    overall_healthy = False
            except Exception as e:
                logger.error(f"❌ スケジューラーヘルスチェックエラー: {e}", exc_info=True)
                health_status['checks']['scheduler'] = {
                    'status': 'error',
                    'error': str(e)
                }
                overall_healthy = False
            
            # 全体のステータスを更新
            health_status['status'] = 'healthy' if overall_healthy else 'degraded'
            
            # HTTPステータスコードを決定（アプリが起動していれば200を返す）
            http_status = 200  # degradedでも200を返す（アプリは動作している）
            
            return jsonify(health_status), http_status
        except Exception as e:
            # ヘルスチェック自体が失敗した場合でも、アプリは動作していることを示す
            logger.error(f"❌ ヘルスチェックエラー: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'message': 'Health check failed but app is running'
            }), 200  # アプリは動作しているので200を返す
    
    logger.info("✅ アプリケーション初期化完了（すべてのコンポーネント）")
    return app, scheduler


def main():
    """メイン関数"""
    try:
        # アプリケーションを作成
        app, scheduler = create_app()
        
        # スケジューラーを開始
        if scheduler:
            scheduler.start()
            logger.info("🚀 スケジューラー開始完了")
            logger.info("📅 毎日朝7:00（日本時間）に全トレンドを自動取得します")
        else:
            logger.warning("⚠️ スケジューラーは無効です")
        
        # Flaskアプリを開始
        config = AppConfig.get_config_dict()
        logger.info(f"🚀 アプリケーションをポート {config['PORT']} で起動します")
        app.run(
            debug=config['DEBUG'],
            host=config['HOST'],
            port=config['PORT']
        )
        
    except KeyboardInterrupt:
        logger.info("\n🛑 アプリケーション終了中...")
        if scheduler:
            scheduler.stop()
            logger.info("✅ スケジューラー停止完了")
    except Exception as e:
        logger.error(f"❌ アプリケーション起動エラー: {e}", exc_info=True)
        if scheduler:
            scheduler.stop()


if __name__ == '__main__':
    main()
