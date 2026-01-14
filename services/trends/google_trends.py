import os
import pandas as pd
import pandas_gbq
from google.oauth2 import service_account
from datetime import datetime, timedelta
from database_config import TrendsCache
from dotenv import load_dotenv
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# 環境変数を明示的に読み込み
load_dotenv()

# ロガーの初期化
logger = get_logger(__name__)

class GoogleTrendsManager(BaseTrendsManager):
    """Google Trendsのトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        import json
        import base64
        
        # ベースクラスを初期化（rate_limiterは使用しないため、max_requestsを1に設定）
        super().__init__(service_name='google', max_requests=1, window_seconds=60)
        
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        self.credentials = None
        
        # 方法1: Base64エンコードされた認証情報から読み込み（本番環境用）
        credentials_content = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_CONTENT')
        if credentials_content:
            try:
                # Base64デコード
                decoded_content = base64.b64decode(credentials_content).decode('utf-8')
                credentials_dict = json.loads(decoded_content)
                self.credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                logger.info("  Credentials: GOOGLE_APPLICATION_CREDENTIALS_CONTENTから読み込み済み")
            except Exception as e:
                logger.error(f"❌ Google Trends Credentials (CONTENT) 読み込みエラー: {e}", exc_info=True)
                self.credentials = None
        
        # 方法2: ファイルパスから読み込み（ローカル環境用）
        if not self.credentials:
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path:
                if os.path.exists(credentials_path):
                    try:
                        self.credentials = service_account.Credentials.from_service_account_file(credentials_path)
                        logger.info(f"  Credentials: ファイル {credentials_path} から読み込み済み")
                    except Exception as e:
                        logger.error(f"❌ Google Trends Credentials 読み込みエラー: {e}", exc_info=True)
                        self.credentials = None
                else:
                    logger.warning(f"⚠️ Google Trends Credentials: パスが存在しません ({credentials_path})")
            else:
                logger.warning("⚠️ Google Trends Credentials: GOOGLE_APPLICATION_CREDENTIALS が設定されていません")
        
        if not self.project_id:
            logger.warning("Warning: GOOGLE_CLOUD_PROJECT_IDが設定されていません")
        
        logger.info(f"Google Trends Manager初期化:")
        logger.info(f"  Project ID: {'設定済み' if self.project_id else '未設定'}")
        logger.info(f"  Credentials: {'設定済み' if self.credentials else '未設定'}")
    
    def _fetch_trends(self, region='JP', limit=25, *args, **kwargs):
        """外部APIからGoogle Trendsデータを取得"""
        return self.get_bigquery_trends(region, limit)
    
    def get_trends(self, region='JP', limit=25, force_refresh=False):
        """Google Trendsを取得（キャッシュ優先、フォールバックでBigQuery）"""
        if force_refresh:
            logger.info(f"🔄 Google Trends force_refresh: キャッシュをクリアします")
            self.db.clear_google_trends_cache(region)
        
        # 日本と同じロジックを使用（キャッシュ優先、フォールバックでBigQuery）
        return self.get_cached_trends(region, limit, force_refresh)
    
    def get_bigquery_trends(self, region='JP', limit=25):
        """BigQueryからGoogle Trendsデータを取得"""
        try:
            logger.info(f"=== Google Trends BigQuery取得開始 ===")
            logger.info(f"リクエストパラメータ: region={region}, limit={limit}")
            
            if not self.project_id:
                return {
                    'success': False,
                    'error': 'Google Cloud Project IDが設定されていません',
                    'data': []
                }
            
            # USデータの取得のみに集中
            logger.info("USデータを取得します")
            
            # USデータの場合はtop_termsテーブルを使用
            if region == 'US':
                logger.info(f"{region}のデータを取得するため、top_termsテーブルを使用します")
                query = f"""
            SELECT 
                term as keyword,
                AVG(score) as score,
                'US' as country_code,
                refresh_date,
                ROW_NUMBER() OVER (ORDER BY AVG(score) DESC) as rank
            FROM `bigquery-public-data.google_trends.top_terms`
            WHERE refresh_date = (
                SELECT MAX(refresh_date)
                FROM `bigquery-public-data.google_trends.top_terms`
            )
              AND score IS NOT NULL
            GROUP BY term, refresh_date
            ORDER BY score DESC
            LIMIT {limit}
            """
            else:
                # 日本と同じクエリを使用（国コードを指定）
                logger.info(f"{region}のデータを取得するため、international_top_termsテーブルを使用します")
                query = f"""
            SELECT 
                term as keyword,
                AVG(score) as score,
                country_code,
                refresh_date,
                ROW_NUMBER() OVER (ORDER BY AVG(score) DESC) as rank
            FROM `bigquery-public-data.google_trends.international_top_terms`
            WHERE country_code = '{region}'
              AND refresh_date = (
                SELECT MAX(refresh_date)
                FROM `bigquery-public-data.google_trends.international_top_terms`
                WHERE country_code = '{region}'
              )
              AND score IS NOT NULL
            GROUP BY term, country_code, refresh_date
            ORDER BY score DESC
            LIMIT {limit}
            """
            
            logger.debug(f"BigQueryクエリ実行: {query}")
            
            # BigQueryからデータを取得
            df = pandas_gbq.read_gbq(query, project_id=self.project_id, credentials=self.credentials)
            
            if df.empty:
                logger.warning("❌ Google Trends: USデータが取得できませんでした")
                return {
                    'success': False,
                    'error': 'USデータが取得できませんでした',
                    'data': [],
                    'status': 'api_error',
                    'source': 'BigQuery',
                    'country': region
                }
            
            # データを辞書形式に変換
            trends_data = []
            logger.debug(f"取得したデータの構造確認:")
            logger.debug(f"列名: {df.columns.tolist()}")
            logger.debug(f"データフレームの形状: {df.shape}")
            logger.debug(f"最初の5行: {df.head(5).to_dict('records')}")
            
            # 重複チェック
            unique_keywords = df['keyword'].nunique()
            logger.debug(f"ユニークなキーワード数: {unique_keywords}")
            
            # 重複を排除（念のため）
            seen_keywords = set()
            
            for i, row in df.iterrows():
                keyword = str(row['keyword']).strip()
                if not keyword or keyword == 'nan' or keyword in seen_keywords:
                    continue
                    
                seen_keywords.add(keyword)
                
                # Google検索URLを生成
                google_search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&geo=US"
                
                trends_data.append({
                    'keyword': keyword,
                    'rank': len(trends_data) + 1,  # 連番でランクを設定
                    'popularity': int(row['score']),
                    'score': int(row['score']),
                    'country_code': row['country_code'],
                    'refresh_date': row['refresh_date'].strftime('%Y-%m-%d') if pd.notna(row['refresh_date']) else None,
                    'google_search_url': google_search_url
                })
                
                # 最初の3件だけログ出力
                if len(trends_data) <= 3:
                    logger.debug(f"行 {len(trends_data)}: keyword='{keyword}', rank={len(trends_data)}, score={row['score']}")
                    logger.debug(f"  変換後: rank={len(trends_data)}, popularity={int(row['score'])}")
            
            logger.info(f"✅ Google Trends: {len(trends_data)}件のデータを取得しました (国コード: {region})")
            
            # キャッシュに保存（_save_to_cacheはBaseTrendsManagerが呼び出す）
            self._save_to_cache(trends_data, region=region)
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'success',
                'source': 'BigQuery',
                'country': region,
                'actual_country': region,  # 実際に使用された国コード
                'total_count': len(trends_data)
            }
            
        except Exception as e:
            logger.error(f"❌ Google Trends BigQuery取得エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Google Trends取得に失敗しました: {str(e)}',
                'data': [],
                'status': 'api_error',
                'source': 'BigQuery',
                'country': region,
                'debug_info': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            }
    
    def get_cached_trends(self, region='JP', limit=25, force_refresh=False):
        """Google Trendsデータを取得（キャッシュデータが存在しない場合のみ外部APIを呼び出し）"""
        try:
            logger.info(f"=== Google Trends キャッシュ取得開始 ===")
            logger.info(f"リクエストパラメータ: region={region}, limit={limit}, force_refresh={force_refresh}")
            
            # データベースからキャッシュを取得
            cached_data = self.db.get_google_trends_from_cache(region)
            
            if cached_data:
                # キャッシュデータに検索URLを追加
                for item in cached_data:
                    if 'google_search_url' not in item and 'keyword' in item:
                        keyword = item['keyword']
                        item['google_search_url'] = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                
                logger.info(f"✅ Google Trends: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'total_count': len(cached_data)
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ Google Trends: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': False,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ Google Trends: キャッシュデータが見つかりません。外部APIを呼び出します")
                # キャッシュデータが存在しない場合のみ外部APIを呼び出し
                result = self.get_bigquery_trends(region, limit)
                if result.get('success') and result.get('data'):
                    logger.info(f"✅ Google Trends: 外部APIから{len(result['data'])}件のデータを取得し、キャッシュに保存しました")
                    return {
                        'success': True,
                        'data': result['data'],
                        'status': 'api_fetched',
                        'source': 'BigQuery',
                        'total_count': len(result['data'])
                    }
                else:
                    logger.error(f"❌ Google Trends: 外部APIからデータを取得できませんでした")
                    return {
                        'success': False,
                        'data': [],
                        'status': 'api_error',
                        'source': 'BigQuery',
                        'total_count': 0
                    }
                
        except Exception as e:
            logger.error(f"❌ Google Trends キャッシュ取得エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Google Trends取得に失敗しました: {str(e)}',
                'data': []
            }
    

