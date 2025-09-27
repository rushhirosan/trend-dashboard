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
    PORT = int(os.getenv('FLASK_PORT', 5001))
    
    # データベース設定
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/trends_db')
    
    # API設定
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # その他の設定
    CACHE_VALIDITY_HOURS = int(os.getenv('CACHE_VALIDITY_HOURS', 24))
    MAX_RESULTS = int(os.getenv('MAX_RESULTS', 25))
    
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
            'CACHE_VALIDITY_HOURS': cls.CACHE_VALIDITY_HOURS,
            'MAX_RESULTS': cls.MAX_RESULTS
        }


