import os
import pandas as pd
import pandas_gbq
from google.cloud import bigquery
from datetime import datetime, timedelta
from database_config import TrendsCache
from dotenv import load_dotenv

# 環境変数を明示的に読み込み
load_dotenv()

class GoogleTrendsManager:
    """Google Trendsのトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        self.db = TrendsCache()
        
        if not self.project_id:
            print("Warning: GOOGLE_CLOUD_PROJECT_IDが設定されていません")
        
        print(f"Google Trends Manager初期化:")
        print(f"  Project ID: {'設定済み' if self.project_id else '未設定'}")
    
    def get_trends(self, region='JP', limit=25, force_refresh=False):
        """Google Trendsを取得（キャッシュ優先、フォールバックでBigQuery）"""
        if force_refresh:
            print(f"🔄 Google Trends force_refresh: キャッシュをクリアします")
            self.db.clear_google_trends_cache(region)
        return self.get_cached_trends(region, limit)
    
    def get_bigquery_trends(self, region='JP', limit=25):
        """BigQueryからGoogle Trendsデータを取得"""
        try:
            print(f"=== Google Trends BigQuery取得開始 ===")
            print(f"リクエストパラメータ: region={region}, limit={limit}")
            
            if not self.project_id:
                return {
                    'success': False,
                    'error': 'Google Cloud Project IDが設定されていません',
                    'data': []
                }
            
            # BigQueryクエリ（日本全体のTop 25を取得 - 都道府県を集約）
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
            
            print(f"BigQueryクエリ実行: {query}")
            
            # BigQueryからデータを取得
            df = pandas_gbq.read_gbq(query, project_id=self.project_id)
            
            if df.empty:
                print("❌ Google Trends: データが取得できませんでした")
                return {
                    'success': False,
                    'error': 'データが取得できませんでした',
                    'data': []
                }
            
            # データを辞書形式に変換
            trends_data = []
            for i, row in df.iterrows():
                keyword = row['keyword']
                # Google検索URLを生成
                google_search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                
                trends_data.append({
                    'keyword': keyword,  # keywordフィールドを使用
                    'rank': row['rank'],  # BigQueryから取得したrankを使用
                    'score': int(row['score']),  # 平均スコアを整数に変換
                    'country_code': row['country_code'],
                    'refresh_date': row['refresh_date'].strftime('%Y-%m-%d') if pd.notna(row['refresh_date']) else None,
                    'google_search_url': google_search_url
                })
            
            print(f"✅ Google Trends: {len(trends_data)}件のデータを取得しました")
            
            # キャッシュに保存
            self.db.save_google_trends_to_cache(trends_data, region)
            
            return {
                'success': True,
                'data': trends_data,
                'status': 'success',
                'source': 'bigquery',
                'total_count': len(trends_data)
            }
            
        except Exception as e:
            print(f"❌ Google Trends BigQuery取得エラー: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': f'Google Trends取得に失敗しました: {str(e)}',
                'data': []
            }
    
    def get_cached_trends(self, region='JP', limit=25):
        """キャッシュからGoogle Trendsデータを取得"""
        try:
            print(f"=== Google Trends キャッシュ取得開始 ===")
            print(f"リクエストパラメータ: region={region}, limit={limit}")
            
            # データベースからキャッシュを取得
            cached_data = self.db.get_google_trends_from_cache(region)
            
            if cached_data:
                # キャッシュデータに検索URLを追加
                for item in cached_data:
                    if 'google_search_url' not in item and 'keyword' in item:
                        keyword = item['keyword']
                        item['google_search_url'] = f"https://www.google.com/search?q={keyword.replace(' ', '+')}"
                
                print(f"✅ Google Trends: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'total_count': len(cached_data)
                }
            else:
                print("❌ Google Trends: キャッシュデータが見つかりません。実際のAPIを呼び出します")
                # キャッシュが空の場合、実際のGoogle Trends APIを呼び出す
                result = self.get_bigquery_trends(region, limit)
                # BigQueryからデータを取得できた場合、キャッシュに保存
                if result['success']:
                    self.db.save_google_trends_to_cache(result['data'], region)
                return result
                
        except Exception as e:
            print(f"❌ Google Trends キャッシュ取得エラー: {e}")
            print("❌ Google Trends: キャッシュ取得に失敗しました。実際のAPIを呼び出します")
            # キャッシュ取得に失敗した場合、実際のGoogle Trends APIを呼び出す
            result = self.get_bigquery_trends(region, limit)
            # BigQueryからデータを取得できた場合、キャッシュに保存
            if result.get('success') and result.get('data'):
                self.db.save_google_trends_to_cache(result['data'], region)
            return result
    

