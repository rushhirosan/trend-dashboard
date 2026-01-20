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
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'google_trends'
    
    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        try:
            region = kwargs.get('region', 'JP')
            cached_data = self.db.get_google_trends_from_cache(region)
            
            # cached_dataがNoneの場合はデータベースエラー
            if cached_data is None:
                logger.error(f"❌ Google Trends: データベースからキャッシュを取得する際にエラーが発生しました")
                return None
            
            # キャッシュデータに検索URLを追加（存在しない場合のみ）
            if cached_data:
                for item in cached_data:
                    if 'google_search_url' not in item and 'keyword' in item:
                        keyword = item['keyword']
                        item['google_search_url'] = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
            
            return cached_data
        except Exception as e:
            logger.error(f"❌ Google Trends: キャッシュ取得エラー: {e}", exc_info=True)
            return None
    
    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.save_google_trends_to_cache(data, region)
        except Exception as e:
            logger.error(f"❌ Google Trends キャッシュ保存エラー: {e}", exc_info=True)
            return False
    
    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            region = kwargs.get('region', 'JP')
            return self.db.clear_google_trends_cache(region)
        except Exception as e:
            logger.error(f"❌ Google Trends キャッシュクリアエラー: {e}", exc_info=True)
            return False
    
    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Google Trends: cache_status更新エラー: {e}")
            return False
    
    def _fetch_trends(self, region='JP', limit=25, *args, **kwargs):
        """外部APIからGoogle Trendsデータを取得"""
        return self.get_bigquery_trends(region, limit)
    
    def get_trends(self, region='JP', limit=25, force_refresh=False):
        """Google Trendsを取得（キャッシュ優先、フォールバックでBigQuery）"""
        # BaseTrendsManagerの共通処理を使用
        # auto_fetch_on_cache_miss=Falseで、キャッシュがない場合はAPIを呼び出さない（既存動作を維持）
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            region=region
        )
        
        # regionパラメータを結果に追加
        if result and isinstance(result, dict):
            result['country'] = region
        return result
    
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
            
            # まず、利用可能な最新のrefresh_dateを確認（デバッグ用）
            if region == 'US':
                check_query = """
                SELECT DISTINCT refresh_date
                FROM `bigquery-public-data.google_trends.top_terms`
                ORDER BY refresh_date DESC
                LIMIT 10
                """
            else:
                check_query = f"""
                SELECT DISTINCT refresh_date
                FROM `bigquery-public-data.google_trends.international_top_terms`
                WHERE country_code = '{region}'
                ORDER BY refresh_date DESC
                LIMIT 10
                """
            
            try:
                check_df = pandas_gbq.read_gbq(check_query, project_id=self.project_id, credentials=self.credentials)
                if not check_df.empty:
                    available_dates = []
                    for date_val in check_df['refresh_date'].head(5):
                        if isinstance(date_val, pd.Timestamp):
                            date_str = date_val.strftime('%Y-%m-%d')
                            days_old = (datetime.now() - date_val.to_pydatetime()).days
                            available_dates.append(f"{date_str} ({days_old}日前)")
                        else:
                            available_dates.append(str(date_val))
                    logger.info(f"📅 利用可能な最新のrefresh_date（上位5件）: {', '.join(available_dates)}")
            except Exception as e:
                logger.warning(f"⚠️ refresh_date確認クエリエラー: {e}")
            
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
                logger.warning(f"❌ Google Trends: {region}データが取得できませんでした")
                return {
                    'success': False,
                    'error': f'{region}データが取得できませんでした',
                    'data': [],
                    'status': 'api_error',
                    'source': 'BigQuery',
                    'country': region
                }
            
            # refresh_dateを確認（データ変換の前）
            refresh_dates = df['refresh_date'].unique() if 'refresh_date' in df.columns else []
            latest_refresh_date = None
            days_old = None
            latest_refresh_date_str = None
            
            if len(refresh_dates) > 0:
                latest_refresh_date = max(refresh_dates)
                if isinstance(latest_refresh_date, pd.Timestamp):
                    days_old = (datetime.now() - latest_refresh_date.to_pydatetime()).days
                    latest_refresh_date_str = latest_refresh_date.strftime('%Y-%m-%d')
                    logger.info(f"📅 Google Trends: BigQueryデータのrefresh_date = {latest_refresh_date_str} ({days_old}日前, region={region})")
                    
                    # 7日以上古い場合はデータを返さない
                    if days_old >= 7:
                        error_msg = f"データが{days_old}日前のもので、表示可能期間（7日）を超えています。BigQueryのデータは通常数日遅れで更新されるため、最新データが利用可能になるまでお待ちください。"
                        logger.warning(f"⚠️ Google Trends ({region}): {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg,
                            'data': [],
                            'status': 'data_too_old',
                            'source': 'BigQuery',
                            'country': region,
                            'refresh_date': latest_refresh_date_str,
                            'days_old': days_old
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
                
                # Google検索URLを生成（regionに応じてgeoパラメータを設定）
                geo_param = region if region in ['JP', 'US'] else 'US'
                google_search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&geo={geo_param}"
                
                # refresh_dateを取得
                refresh_date_str = row['refresh_date'].strftime('%Y-%m-%d') if pd.notna(row['refresh_date']) else None
                if refresh_date_str and not latest_refresh_date_str:
                    latest_refresh_date_str = refresh_date_str
                
                trends_data.append({
                    'keyword': keyword,
                    'rank': len(trends_data) + 1,  # 連番でランクを設定
                    'popularity': int(row['score']),
                    'score': int(row['score']),
                    'country_code': row['country_code'],
                    'refresh_date': refresh_date_str,
                    'google_search_url': google_search_url
                })
                
                # 最初の3件だけログ出力
                if len(trends_data) <= 3:
                    logger.debug(f"行 {len(trends_data)}: keyword='{keyword}', rank={len(trends_data)}, score={row['score']}, refresh_date={refresh_date_str}")
                    logger.debug(f"  変換後: rank={len(trends_data)}, popularity={int(row['score'])}")
            
            # データの古さに応じてステータスとメッセージを設定
            status = 'success'
            warning_message = None
            
            if days_old is not None:
                if days_old > 3:
                    # 3-7日: 警告とともに表示
                    status = 'data_stale'
                    warning_message = f"⚠️ このデータは{days_old}日前のものです。BigQueryのデータは通常数日遅れで更新されます。"
                    logger.warning(f"⚠️ Google Trends ({region}): {warning_message}")
                else:
                    # 3日以内: 通常表示
                    logger.info(f"✅ Google Trends ({region}): データは{days_old}日前のもので、問題ありません")
            
            logger.info(f"✅ Google Trends: {len(trends_data)}件のデータを取得しました (国コード: {region}, データ日付: {latest_refresh_date_str})")
            
            # キャッシュに保存はBaseTrendsManager.get_trends()が自動的に行うため、ここでは不要
            
            return {
                'success': True,
                'data': trends_data,
                'status': status,
                'source': 'BigQuery',
                'country': region,
                'actual_country': region,  # 実際に使用された国コード
                'total_count': len(trends_data),
                'refresh_date': latest_refresh_date_str,  # データの日付
                'data_date': latest_refresh_date_str,  # データの日付（互換性のため）
                'days_old': days_old,  # データの古さ（日数）
                'warning': warning_message  # 警告メッセージ（3-7日の場合のみ）
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
    

