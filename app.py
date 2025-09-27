"""
Trends Dashboard - メインアプリケーション
機能別に分割されたモジュールを使用
"""

from flask import Flask, render_template
from config.app_config import AppConfig
from config.database_config import DatabaseConfig
from managers.trend_managers import initialize_managers
from routes.trend_routes import trend_bp
from routes.data_routes import data_bp
from services.subscription.subscription_routes import subscription_bp
from services.scheduler.scheduler_manager import TrendsScheduler


def create_app():
    """Flaskアプリケーションを作成"""
    app = Flask(__name__)
    
    # 設定を適用
    config = AppConfig.get_config_dict()
    app.config.update(config)
    
    # Blueprintを登録
    app.register_blueprint(trend_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(subscription_bp)
    
    # データベースを初期化
    cache = DatabaseConfig.init_database()
    if not cache:
        print("⚠️ データベース初期化に失敗しました")
    
    # BigQueryクライアントを初期化
    bigquery_client = DatabaseConfig.init_bigquery_client()
    if not bigquery_client:
        print("⚠️ BigQueryクライアント初期化に失敗しました")
    
    # マネージャーを初期化
    managers = initialize_managers()
    
    # スケジューラーを初期化
    try:
        scheduler = TrendsScheduler(app)
        print("✅ スケジューラー初期化完了")
    except Exception as e:
        print(f"❌ スケジューラー初期化エラー: {e}")
        scheduler = None
    
    # ルートを定義
    @app.route('/')
    def index():
        """メインページ"""
        return render_template('index.html')
    
    @app.route('/us')
    def us_trends():
        """アメリカトレンドページ"""
        return render_template('us_trends.html')
    
    @app.route('/data-status')
    def data_status():
        """データ鮮度情報ページ"""
        return render_template('data-status.html')
    
    return app, scheduler


def main():
    """メイン関数"""
    try:
        # アプリケーションを作成
        app, scheduler = create_app()
        
        # スケジューラーを開始
        if scheduler:
            scheduler.start()
            print("🚀 スケジューラー開始完了")
            print("📅 毎日朝5:00に全トレンドを自動取得します")
        else:
            print("⚠️ スケジューラーは無効です")
        
        # Flaskアプリを開始
        config = AppConfig.get_config_dict()
        print(f"🚀 アプリケーションをポート {config['PORT']} で起動します")
        app.run(
            debug=config['DEBUG'],
            host=config['HOST'],
            port=config['PORT']
        )
        
    except KeyboardInterrupt:
        print("\n🛑 アプリケーション終了中...")
        if scheduler:
            scheduler.stop()
            print("✅ スケジューラー停止完了")
    except Exception as e:
        print(f"❌ アプリケーション起動エラー: {e}")
        if scheduler:
            scheduler.stop()


if __name__ == '__main__':
    main()
