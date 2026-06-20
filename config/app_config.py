"""
アプリケーション設定
Flaskアプリケーションの設定を管理
"""

import os
from dotenv import load_dotenv

# .env を読み込み（このパッケージの親ディレクトリ = プロジェクトルート）
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(_root, '.env'))
load_dotenv()


class AppConfig:
    """アプリケーション設定クラス"""
    
    # Flask設定
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5000))
    
    # データベース設定
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/trends_db')
    
    # API設定
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    GOOGLE_ANALYTICS_ID = os.getenv('GOOGLE_ANALYTICS_ID')
    
    # その他の設定
    CACHE_VALIDITY_HOURS = int(os.getenv('CACHE_VALIDITY_HOURS', 24))
    MAX_RESULTS = int(os.getenv('MAX_RESULTS', 25))
    
    # スケジューラー設定: ローカルでは無効・Fly.ioでは有効（明示指定時はその値を使用）
    _enable_scheduler_env = os.getenv('ENABLE_SCHEDULER')
    if _enable_scheduler_env is not None and _enable_scheduler_env.strip() != '':
        ENABLE_SCHEDULER = _enable_scheduler_env.strip().lower() == 'true'
    else:
        # Fly.io では FLY_APP_NAME が設定される。未設定＝ローカルではスケジューラを動かさない
        ENABLE_SCHEDULER = (os.getenv('FLY_APP_NAME') or '').strip() != ''
    
    # サブスクリプション機能の表示設定（デフォルトは非表示）
    # 今後使う可能性があるため、コードは残すがUIからは非表示
    ENABLE_SUBSCRIPTION_UI = os.getenv('ENABLE_SUBSCRIPTION_UI', 'false').lower() == 'true'
    
    # ローカル開発用: トレンドAPIをダミーデータで上書き（true のとき全トレンドがダミーを返す）
    USE_DUMMY_DATA = os.getenv('USE_DUMMY_DATA', 'false').lower() in ('true', '1', 'yes')
    
    # Buy Me a Coffee設定
    BUY_ME_A_COFFEE_USERNAME = os.getenv('BUY_ME_A_COFFEE_USERNAME', '')
    
    # AIサマリー Fake door（ティーザー + Waitlist モーダル）
    ENABLE_AI_SUMMARY_FAKE_DOOR = os.getenv(
        'ENABLE_AI_SUMMARY_FAKE_DOOR', 'true'
    ).lower() in ('true', '1', 'yes')
    # 本番は approved のみ表示。ローカル DEBUG では draft も可（明示 false で無効化）
    _allow_draft_env = os.getenv('AI_SUMMARY_FAKE_DOOR_ALLOW_DRAFT')
    if _allow_draft_env is not None and _allow_draft_env.strip() != '':
        AI_SUMMARY_FAKE_DOOR_ALLOW_DRAFT = _allow_draft_env.strip().lower() in (
            'true', '1', 'yes'
        )
    else:
        AI_SUMMARY_FAKE_DOOR_ALLOW_DRAFT = DEBUG
    
    @classmethod
    def get_config_dict(cls):
        """設定を辞書形式で取得"""
        return {
            'SECRET_KEY': cls.SECRET_KEY,
            'DEBUG': cls.DEBUG,
            'HOST': cls.HOST,
            'PORT': cls.PORT,
            'DATABASE_URL': cls.DATABASE_URL,
            'GOOGLE_APPLICATION_CREDENTIALS': cls.GOOGLE_APPLICATION_CREDENTIALS,
            'GOOGLE_ANALYTICS_ID': cls.GOOGLE_ANALYTICS_ID,
            'CACHE_VALIDITY_HOURS': cls.CACHE_VALIDITY_HOURS,
            'MAX_RESULTS': cls.MAX_RESULTS,
            'ENABLE_SCHEDULER': cls.ENABLE_SCHEDULER,
            'ENABLE_SUBSCRIPTION_UI': cls.ENABLE_SUBSCRIPTION_UI,
            'USE_DUMMY_DATA': cls.USE_DUMMY_DATA,
            'BUY_ME_A_COFFEE_USERNAME': cls.BUY_ME_A_COFFEE_USERNAME,
            'ENABLE_AI_SUMMARY_FAKE_DOOR': cls.ENABLE_AI_SUMMARY_FAKE_DOOR,
            'AI_SUMMARY_FAKE_DOOR_ALLOW_DRAFT': cls.AI_SUMMARY_FAKE_DOOR_ALLOW_DRAFT,
        }


