"""
データベース設定
データベース初期化とBigQueryクライアント設定
"""

import os
from google.cloud import bigquery


class DatabaseConfig:
    """データベース設定クラス"""
    
    @staticmethod
    def init_database():
        """データベースを初期化"""
        try:
            # TrendsCacheクラスを動的にインポート
            from services.trends.google_trends import TrendsCache
            cache = TrendsCache()
            cache.init_database()
            print("✅ データベース初期化完了")
            return cache
        except Exception as e:
            print(f"❌ データベース初期化エラー: {e}")
            return None
    
    @staticmethod
    def init_bigquery_client():
        """BigQueryクライアントを初期化"""
        try:
            # Google Cloud認証ファイルのパスを設定
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                print(f"Google Cloud認証ファイル設定: {credentials_path}")
            else:
                print("⚠️ Google Cloud認証ファイルが見つかりません")
            
            # BigQueryクライアントを作成
            client = bigquery.Client()
            print("✅ BigQueryクライアント初期化完了")
            return client
        except Exception as e:
            print(f"❌ BigQueryクライアント初期化エラー: {e}")
            return None

