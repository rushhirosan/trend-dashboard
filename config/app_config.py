"""
アプリケーション設定
Flaskアプリケーションの設定を管理
"""

import os
from dotenv import load_dotenv

# .envファイルを読み込み
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
    
    # スケジューラー設定（デフォルトは有効）
    ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'
    
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
            'ENABLE_SCHEDULER': cls.ENABLE_SCHEDULER
        }


