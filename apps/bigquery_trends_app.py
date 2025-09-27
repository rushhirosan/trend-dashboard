import streamlit as st
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
import pandas as pd
import pandas_gbq
from google.cloud import bigquery
import sys
import os

# PostgreSQL環境変数を直接設定
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'trends_cache'
os.environ['DB_USER'] = 'trends_user'
os.environ['DB_PASSWORD'] = 'trends123'

# 親ディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# キャッシュシステムをインポート
from database_config import TrendsCache

# キャッシュインスタンスを初期化
@st.cache_resource
def init_cache():
    try:
        return TrendsCache()
    except Exception as e:
        print(f"キャッシュシステム初期化エラー: {e}")
        return None

# BigQueryクライアントの初期化（認証なしでテスト用）
@st.cache_resource
def init_bigquery_client():
    """
    BigQueryクライアントを初期化
    """
    try:
        client = bigquery.Client()
        return client, "success"
    except Exception as e:
        print(f"BigQueryクライアント初期化エラー: {e}")
        return None, "auth_error"

def get_trends_from_bigquery(country_code: str, is_rising: bool = False):
    """BigQueryからトレンドデータを取得（キャッシュシステム使用）"""
    client, status = init_bigquery_client()
    if status != "success":
        return None, "auth_error"
    
    cache = init_cache()
    
    # 最新の週を取得
    latest_date_query = f"""
    SELECT MAX(week) as latest_date
    FROM `bigquery-public-data.google_trends.international_top_terms`
    WHERE country_code = '{country_code}'
    """
    
    try:
        latest_date_df = client.query(latest_date_query).to_dataframe()
        if latest_date_df.empty:
            return None, "no_data"
        
        latest_date = latest_date_df.iloc[0]['latest_date']
        latest_date_str = latest_date.strftime('%Y-%m-%d')
        
        # キャッシュが有効かチェック
        if cache: # cacheがNoneでないかチェック
            if cache.is_cache_valid(country_code):
                print(f"{country_code}のキャッシュが有効です。DBから取得します。")
                cached_data = cache.get_cached_trends(country_code, latest_date_str)
                if cached_data:
                    # キャッシュデータをDataFrameに変換
                    df = pd.DataFrame(cached_data)
                    return df, "cached"
        
        # キャッシュが無効または存在しない場合、BigQueryから取得
        print(f"{country_code}のキャッシュが無効です。BigQueryから取得します。")
        
        # トレンドデータを取得するクエリ
        trends_query = f"""
        WITH ranked_terms AS (
            SELECT 
                term,
                SUM(score) as total_score,
                COUNT(DISTINCT region_code) as region_count,
                ROW_NUMBER() OVER (ORDER BY SUM(score) DESC) as national_rank
            FROM `bigquery-public-data.google_trends.international_top_terms`
            WHERE country_code = '{country_code}' 
                AND week = '{latest_date}'
                AND term IS NOT NULL 
                AND term != ''
            GROUP BY term
            HAVING COUNT(DISTINCT region_code) >= 3
        )
        SELECT 
            term,
            national_rank as rank,
            total_score as score,
            region_count,
            '{latest_date_str}' as week,
            '{country_code}' as country_code,
            'Japan' as country_name
        FROM ranked_terms
        ORDER BY national_rank ASC
        LIMIT 25
        """
        
        trends_df = client.query(trends_query).to_dataframe()
        
        if not trends_df.empty:
            # データをキャッシュに保存
            trends_data = trends_df.to_dict('records')
            if cache: # cacheがNoneでないかチェック
                cache.save_trends_data(country_code, trends_data, latest_date_str)
                print(f"{country_code}のデータをキャッシュに保存しました")
        
        return trends_df, "fresh"
        
    except Exception as e:
        print(f"BigQueryからのデータ取得に失敗しました: {str(e)}")
        return None, "error"

def get_sample_data(country_code, is_rising=True):
    """
    サンプルデータを返す（認証エラー時のフォールバック）
    """
    if country_code == 'JP':
        if is_rising:
            sample_data = [
                {'term': 'AI', 'rank': 1, 'score': 95},
                {'term': 'ChatGPT', 'rank': 2, 'score': 88},
                {'term': '機械学習', 'rank': 3, 'score': 82},
                {'term': 'データサイエンス', 'rank': 4, 'score': 78},
                {'term': 'Python', 'rank': 5, 'score': 75}
            ]
        else:
            sample_data = [
                {'term': '天気', 'rank': 1, 'score': 100},
                {'term': 'ニュース', 'rank': 2, 'score': 95},
                {'term': 'YouTube', 'rank': 3, 'score': 90},
                {'term': 'Google', 'rank': 4, 'score': 85},
                {'term': '地図', 'rank': 5, 'score': 80}
            ]
    else:
        if is_rising:
            sample_data = [
                {'term': 'AI', 'rank': 1, 'score': 95},
                {'term': 'ChatGPT', 'rank': 2, 'score': 88},
                {'term': 'Machine Learning', 'rank': 3, 'score': 82},
                {'term': 'Data Science', 'rank': 4, 'score': 78},
                {'term': 'Python', 'rank': 5, 'score': 75}
            ]
        else:
            sample_data = [
                {'term': 'Weather', 'rank': 1, 'score': 100},
                {'term': 'News', 'rank': 2, 'score': 95},
                {'term': 'YouTube', 'rank': 3, 'score': 90},
                {'term': 'Google', 'rank': 4, 'score': 85},
                {'term': 'Maps', 'rank': 5, 'score': 80}
            ]
    
    return pd.DataFrame(sample_data), "sample"

def app():
    """
    メインアプリケーション
    """
    st.title(':chart_with_upwards_trend: Google Trends via BigQuery')
    st.markdown("BigQueryの公開データセットを使用してGoogle Trendsのデータを取得します")
    
    # 国選択
    country_options = {
        'Japan': 'JP',
        'United States': 'US', 
        'United Kingdom': 'GB',
        'India': 'IN',
        'Australia': 'AU',
        'Germany': 'DE'
    }
    
    selected_country = st.selectbox(
        '国を選択してください:',
        list(country_options.keys())
    )
    
    # トレンドタイプ選択
    trend_type = st.radio(
        'トレンドタイプ:',
        ['Top 25 (全体)', 'Top 25 Rising (急上昇)'],
        horizontal=True
    )
    
    is_rising = trend_type == 'Top 25 Rising (急上昇)'
    
    if selected_country:
        country_code = country_options[selected_country]
        
        with st.spinner(f'{selected_country}の{trend_type}を取得中...'):
            trends_df, status = get_trends_from_bigquery(country_code, is_rising)
            
            # BigQueryが失敗した場合のみサンプルデータを使用
            if status in ["auth_error", "error", "no_data"]:
                st.warning("BigQueryからの取得に失敗しました。サンプルデータを表示します。")
                trends_df, status = get_sample_data(country_code, is_rising)
        
        # 結果を表示
        if trends_df is not None and not trends_df.empty:
            # データソースとキャッシュ状態を表示
            if status == "cached":
                st.success(f"✅ {selected_country}のトレンドデータをキャッシュから取得しました！")
                cache = init_cache()
                if cache: # cacheがNoneでないかチェック
                    cache_info = cache.get_cache_info(country_code)
                    if cache_info:
                        st.info(f"📅 最終更新: {cache_info['last_updated'].strftime('%Y-%m-%d %H:%M')} | 📊 データ数: {cache_info['data_count']}件")
            elif status == "fresh":
                st.success(f"🆕 {selected_country}のトレンドデータをBigQueryから新規取得しました！")
            else:
                st.success(f"✅ {selected_country}のトレンドデータを取得しました！")
            
            # データフレームを表示
            st.subheader("📊 トレンドキーワード")
            
            # シンプルな表示（インデックス番号は非表示）
            display_df = trends_df[['rank', 'term', 'score']].copy()
            display_df.columns = ['順位', 'キーワード', '総スコア']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # スコアの棒グラフ
            st.subheader("📈 スコア分布")
            
            # 日本語フォント設定（macOS用）
            try:
                plt.rcParams['font.family'] = 'Hiragino Sans'
            except:
                try:
                    plt.rcParams['font.family'] = 'Hiragino Sans GB'
                except:
                    plt.rcParams['font.family'] = 'sans-serif'
            
            plt.rcParams['axes.unicode_minus'] = False
            
            fig, ax = plt.subplots(figsize=(12, 6))
            bars = ax.bar(range(len(trends_df)), trends_df['score'])
            ax.set_xlabel('キーワード')
            ax.set_ylabel('総スコア')
            ax.set_title(f'{selected_country}のトレンドキーワードスコア')
            ax.set_xticks(range(len(trends_df)))
            ax.set_xticklabels(trends_df['term'], rotation=45, ha='right')
            
            # バーの上にスコアを表示
            for i, bar in enumerate(bars):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{int(height)}', ha='center', va='bottom')
            
            plt.tight_layout()
            st.pyplot(fig)
        else:
            st.warning("データが取得できませんでした。")
    
    else:
        st.info("国を選択してください")

if __name__ == "__main__":
    app() 