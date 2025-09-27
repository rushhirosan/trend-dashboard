from datetime import datetime, timedelta, timezone
import os
from flask import Flask, jsonify, request, render_template
from database_config import TrendsCache
from subscription_routes import subscription_bp
from youtube_trends import YouTubeTrendsManager
import pandas as pd
import pandas_gbq
from google.cloud import bigquery
import json
import traceback
from dotenv import load_dotenv
from music_trends import MusicTrendsManager
from news_trends import NewsTrendsManager
from worldnews_trends import WorldNewsTrendsManager
from podcast_trends import PodcastTrendsManager
from rakuten_trends import RakutenTrendsManager
# from reddit_trends import RedditTrendsManager  # ファイルが削除されたため無効化
from hatena_trends import HatenaTrendsManager
from twitch_trends import TwitchTrendsManager

# .envファイルから環境変数を読み込み
load_dotenv()

# Anthropic APIキーを設定
# anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# YouTube Data APIキーを環境変数から取得
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# PostgreSQL環境変数を直接設定
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'trends_cache'
os.environ['DB_USER'] = 'trends_user'
os.environ['DB_PASSWORD'] = 'trends123'

# World News API環境変数を直接設定
os.environ['WORLDNEWS_API_KEY'] = '899e679570a543549d279dc9abe3394a'

# Google Cloud環境変数を直接設定（.envファイルから読み込み済み）
# os.environ['GOOGLE_CLOUD_PROJECT_ID'] = 'trending-469304'

# 親ディレクトリをパスに追加
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# キャッシュシステムをインポート
from database_config import TrendsCache
from youtube_trends import YouTubeTrendsManager

app = Flask(__name__)

# サブスクリプションBlueprintを登録
app.register_blueprint(subscription_bp)

# キャッシュシステムのインスタンスを作成
cache = TrendsCache()

# データベース初期化（エラーを無視）
try:
    cache.init_database()
except Exception as e:
    print(f"データベース初期化をスキップ: {e}")

# BigQueryクライアントの初期化
def init_bigquery_client():
    try:
        # Google Cloud認証ファイルのパスを設定
        # .envファイルから環境変数を読み込み
        google_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', './trending-469304-23cc672761b0.json')
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = google_creds
        client = bigquery.Client()
        return client, "success"
    except Exception as e:
        print(f"BigQueryクライアント初期化エラー: {e}")
        return None, "auth_error"

def get_trends_from_bigquery(country_code: str, is_rising: bool = False):
    """BigQueryからトレンドデータを取得（キャッシュシステム使用）"""
    print(f"BigQueryから{country_code}のデータを取得開始")
    
    # まずキャッシュをチェック（BigQueryクエリの前に実行）
    cache = init_cache()
    if cache and cache.is_cache_valid(country_code):
        print(f"{country_code}のキャッシュが有効です。DBから取得します。")
        try:
            # データベースから最新のrefresh_dateを直接取得
            conn = cache.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT refresh_date 
                FROM trends_cache 
                WHERE country_code = %s 
            ORDER BY refresh_date DESC
                LIMIT 1
            """, (country_code,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            
            if result:
                latest_date = result[0]
                cached_data = cache.get_cached_trends(country_code, latest_date)
                if cached_data:
                    print(f"キャッシュから{len(cached_data)}件のデータを取得しました")
                    # キャッシュデータをDataFrameに変換
                    df = pd.DataFrame(cached_data)
                    # キャッシュデータも確実にソート
                    df = df.sort_values('rank', ascending=True).reset_index(drop=True)
                    print(f"キャッシュデータをrankでソートしました")
                    return df, "cached"
                else:
                    print("キャッシュデータが空でした")
            else:
                print("最新の日付を取得できませんでした")
        except Exception as e:
            print(f"キャッシュデータ取得エラー: {e}")
    print("⚠️ 現在はキャッシュのみ使用可能です。BigQueryクエリは無効化されています。")
    return None, "no_cache"



def get_keyword_explanation(keyword: str, country_code: str = 'JP') -> dict:
    """キーワードの説明を生成（簡素化版）"""
    try:
        google_search_url = f"https://www.google.com/search?q={keyword}"
        
        return {
            'explanation': "",  # 説明文は空
            'google_search_url': google_search_url
        }
        
    except Exception as e:
        print(f"説明生成エラー: {e}")
        return {
            'explanation': "",
            'google_search_url': f"https://www.google.com/search?q={keyword}"
        }



def get_trends_with_search_urls(trends_data: list, country_code: str) -> list:
    """トレンドデータにGoogle検索URLを追加"""
    for i, trend in enumerate(trends_data):
        search_data = get_keyword_explanation(trend['term'], country_code)
        trend['google_search_url'] = search_data['google_search_url']
        # 説明列は削除（不要）
        if 'explanation' in trend:
            del trend['explanation']
    
    return trends_data

# 各マネージャーの初期化（エラーハンドリング付き）
try:
    # YouTube Trends管理インスタンスを作成
    youtube_manager = YouTubeTrendsManager()
    print("✅ YouTube Manager初期化完了")
except Exception as e:
    print(f"❌ YouTube Manager初期化エラー: {e}")
    youtube_manager = None

try:
    # 音楽トレンド Manager
    music_manager = MusicTrendsManager()
    print("✅ Music Manager初期化完了")
except Exception as e:
    print(f"❌ Music Manager初期化エラー: {e}")
    music_manager = None

try:
    # ニューストレンド Manager
    news_manager = NewsTrendsManager()
    print("✅ News Manager初期化完了")
except Exception as e:
    print(f"❌ News Manager初期化エラー: {e}")
    news_manager = None

try:
    # World News API Manager
    worldnews_manager = WorldNewsTrendsManager()
    print("✅ World News Manager初期化完了")
except Exception as e:
    print(f"❌ World News Manager初期化エラー: {e}")
    worldnews_manager = None

try:
    # ポッドキャストトレンド Manager
    podcast_manager = PodcastTrendsManager()
    print("✅ Podcast Manager初期化完了")
except Exception as e:
    print(f"❌ Podcast Manager初期化エラー: {e}")
    podcast_manager = None

try:
    # 楽天トレンド Manager
    rakuten_manager = RakutenTrendsManager()
    print("✅ Rakuten Manager初期化完了")
except Exception as e:
    print(f"❌ Rakuten Manager初期化エラー: {e}")
    rakuten_manager = None

try:
    # はてなブックマークトレンド Manager
    hatena_manager = HatenaTrendsManager()
    print("✅ Hatena Manager初期化完了")
except Exception as e:
    print(f"❌ Hatena Manager初期化エラー: {e}")
    hatena_manager = None

try:
    # Twitchトレンド Manager
    twitch_manager = TwitchTrendsManager()
    print("✅ Twitch Manager初期化完了")
except Exception as e:
    print(f"❌ Twitch Manager初期化エラー: {e}")
    twitch_manager = None

def init_cache():
    try:
        return TrendsCache()
    except Exception as e:
        print(f"キャッシュシステム初期化エラー: {e}")
        return None

def get_youtube_trends(region_code: str = 'JP', max_results: int = 25):
    """YouTubeのトレンド動画を取得"""
    return youtube_manager.get_trends(region_code, max_results)

def get_youtube_rising_trends(region_code: str = 'JP', max_results: int = 25):
    """YouTubeの急上昇トレンド動画を取得（投稿日時と視聴回数から推定）"""
    return youtube_manager.get_rising_trends(region_code, max_results)

def get_spotify_trends():
    """Spotifyのトレンドを取得"""
    try:
        return music_manager.get_trends()
    except Exception as e:
        print(f"Spotify トレンド取得エラー: {e}")
        return None

def get_world_news_trends():
    """World Newsのトレンドを取得"""
    try:
        return worldnews_manager.get_trends()
    except Exception as e:
        print(f"World News トレンド取得エラー: {e}")
        return None

def get_hatena_trends():
    """はてなブックマークのトレンドを取得"""
    try:
        return hatena_manager.get_trends()
    except Exception as e:
        print(f"はてなブックマーク トレンド取得エラー: {e}")
        return None

def get_twitch_trends():
    """Twitchのトレンドを取得"""
    try:
        return twitch_manager.get_trends(25)
    except Exception as e:
        print(f"Twitch トレンド取得エラー: {e}")
        return None

def get_rakuten_trends():
    """楽天のトレンドを取得"""
    try:
        return rakuten_manager.get_trends()
    except Exception as e:
        print(f"楽天 トレンド取得エラー: {e}")
        return None

def get_podcast_trends():
    """Podcastのトレンドを取得"""
    try:
        return podcast_manager.get_trends('best_podcasts')
    except Exception as e:
        print(f"Podcast トレンド取得エラー: {e}")
        return None

@app.route('/')
def index():
    """メインページ（日本）"""
    return render_template('index.html')

@app.route('/us')
def us_trends():
    """アメリカページ"""
    return render_template('us.html')

@app.route('/data-status')
def data_status():
    """データ鮮度情報ページ"""
    return render_template('data-status.html')

@app.route('/subscription')
def subscription():
    """サブスクリプションページ"""
    return render_template('subscription.html')

@app.route('/api/subscription-status')
def get_subscription_status():
    """サブスクリプション状態を取得するAPIエンドポイント"""
    try:
    # 簡単な実装（実際のDBアクセスは後で実装）
        return jsonify({
            'success': True,
            'subscribed': False,
            'email': None,
            'frequency': None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/google-trends')
def get_google_trends():
    """Google Trendsデータを取得するAPIエンドポイント"""
    country_code = request.args.get('country', 'JP')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 Google Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_trends_cache_by_country(country_code)
                print(f"✅ Google Trends 古いキャッシュデータを削除しました")
        # まず直接データベースからデータを確認
        cache = init_cache()
        if cache:
            try:
                conn = cache.get_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT refresh_date 
                    FROM trends_cache 
                    WHERE country_code = %s 
                    ORDER BY refresh_date DESC
                    LIMIT 1
                """, (country_code,))
                result = cur.fetchone()
                cur.close()
                conn.close()
                
                if result:
                    latest_date = result[0]
                    cached_data = cache.get_cached_trends(country_code, latest_date)
                    if cached_data:
                        print(f"キャッシュから{len(cached_data)}件のデータを取得しました")
                        # キャッシュデータをDataFrameに変換
                        import pandas as pd
                        df = pd.DataFrame(cached_data)
                        # キャッシュデータも確実にソート
                        df = df.sort_values('rank', ascending=True).reset_index(drop=True)
                        print(f"キャッシュデータをrankでソートしました")
                        
                        # データをJSON形式に変換
                        trends_data = df.to_dict('records')
                        
                        # Google検索URLを生成
                        trends_data = get_trends_with_search_urls(trends_data, country_code)
                        print(f"キャッシュからデータを取得しました。Google検索URLも含まれています。")
                        
                        # キャッシュ情報を取得
                        cache_info = cache.get_cache_info(country_code)
                        
                        return jsonify({
                            'success': True,
                            'data': trends_data,
                            'status': 'cached',
                            'country_code': country_code,
                            'trend_type': 'top',
                            'cache_info': cache_info
                        })
            except Exception as e:
                print(f"直接データベース取得エラー: {e}")
        
        # データが取得できなかった場合、BigQueryから直接取得
        print(f"キャッシュデータが存在しません。BigQueryから直接取得します")
        
        # Google Trends Managerを使用してBigQueryから直接取得
        from google_trends import GoogleTrendsManager
        trends_manager = GoogleTrendsManager()
        
        result = trends_manager.get_bigquery_trends(country_code, 25)
        
        if result['success']:
            # データをJSON形式に変換
            trends_data = result['data']
            
            # Google検索URLを生成
            trends_data = get_trends_with_search_urls(trends_data, country_code)
            
            return jsonify({
                'success': True,
                'data': trends_data,
                'status': 'fresh',
                'country_code': country_code,
                'trend_type': 'top',
                'source': 'bigquery'
            })
        else:
        return jsonify({
            'success': False,
                'error': result['error'],
                'country_code': country_code,
                'trend_type': 'top'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/youtube-trends')
def get_youtube_trends_api():
    """YouTubeのトレンド動画を取得するAPI"""
    print("=== YouTube Trends API 呼び出し開始 ===")
    region = request.args.get('region', 'JP')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    print(f"リクエストパラメータ: region={region}, force_refresh={force_refresh}")
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 YouTube Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_youtube_trends_cache(region)
                print(f"✅ YouTube Trends 古いキャッシュデータを削除しました")
        
        # YouTube Trends Managerを使用してデータを取得
        print("YouTube Trends Managerを使用してデータを取得します")
        if youtube_manager:
            result = youtube_manager.get_trends(region, 25, force_refresh)
            print(f"YouTube Manager結果タイプ: {type(result)}")
            
            # YouTube Managerがリストを返す場合の処理
            if isinstance(result, list):
                print(f"YouTube Managerから{len(result)}件のデータを取得しました")
                return jsonify({
                    'success': True,
                    'status': 'fresh' if force_refresh else 'cached',
                'region_code': region,
                    'data': result
                })
            # 辞書を返す場合の処理
            elif isinstance(result, dict):
                if result.get('error'):
                    print(f"YouTube Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'region_code': region
                    })
                elif result.get('data'):
                    print(f"YouTube Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'unknown'),
                        'region_code': region,
                        'data': result['data'],
                        'cache_info': result.get('cache_info')
                    })
        else:
                    print("YouTube Managerからデータを取得できませんでした")
                    return jsonify({
                        'success': False,
                        'error': 'YouTube Managerからデータを取得できませんでした',
                        'region_code': region
                    })
            else:
                print(f"YouTube Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'YouTube Manager予期しない戻り値タイプ: {type(result)}',
                    'region_code': region
                })
        else:
            return jsonify({
                'success': False,
                'error': 'YouTube Managerが初期化されていません',
                'region_code': region
            })
            
    except Exception as e:
        print(f"❌ YouTube API エラー: {e}")
        import traceback
        traceback.print_exc()
    return jsonify({
        'success': False,
            'error': f'YouTube APIでエラーが発生しました: {str(e)}',
            'region_code': region
        }), 500

@app.route('/api/youtube-rising-trends')
def api_youtube_rising_trends():
    """YouTube急上昇トレンドAPI"""
    try:
        region = request.args.get('region', 'JP')
        result = youtube_manager.get_rising_trends(region)
        
        if 'error' in result:
            return jsonify({'error': result['error']}), 400
        
        return jsonify(result)
        
    except Exception as e:
        print(f"YouTube急上昇トレンドAPIエラー: {e}")
        return jsonify({'error': 'YouTube急上昇トレンドの取得に失敗しました'}), 500

@app.route('/api/music-trends')
def api_music_trends():
    """音楽トレンドAPI（1日1回のみAPI呼び出し）"""
    try:
        service = request.args.get('service', 'spotify')
        region = request.args.get('region', 'JP')
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        print(f"=== Music API 呼び出し開始 ===")
        print(f"リクエストパラメータ: service={service}, region={region}, force_refresh={force_refresh}")
        
        # 1日1回のみAPIを呼び出し、その後はキャッシュを使用
        try:
            if music_manager:
                result = music_manager.get_trends(service, region, force_refresh)
                print(f"JPの{service}音楽トレンドデータをキャッシュから取得しました")
                return jsonify(result)
            else:
                return jsonify({'error': 'Music Managerが初期化されていません'})
        except Exception as e:
            print(f"音楽トレンド取得エラー: {e}")
            return jsonify({'error': f'音楽トレンドの取得に失敗しました: {str(e)}'})
    
    except Exception as e:
        print(f"音楽トレンドAPIエラー: {e}")
        return jsonify({'error': '音楽トレンドの取得に失敗しました'}), 500

@app.route('/api/refresh-all', methods=['POST'])
def refresh_all_trends():
    """全トレンドデータを強制更新するAPIエンドポイント"""
    try:
        print("=== 全トレンドデータ強制更新開始 ===")
        
        # スケジューラーの手動実行
        if scheduler:
            scheduler._fetch_all_trends()
            print("✅ 全トレンドデータの強制更新が完了しました")
            return jsonify({
                'success': True,
                'message': '全トレンドデータの強制更新が完了しました',
                'timestamp': datetime.now().isoformat()
            })
        else:
        return jsonify({
            'success': False,
                'error': 'スケジューラーが初期化されていません'
            }), 500
        
    except Exception as e:
        print(f"強制更新エラー: {e}")
        return jsonify({
            'success': False,
            'error': f'強制更新に失敗しました: {str(e)}'
        }), 500

@app.route('/api/cache/status')
def get_cache_status():
    """キャッシュの状態を取得するAPIエンドポイント"""
    country_code = request.args.get('country', 'JP')
    
    try:
        cache_info = cache.get_cache_info(country_code)
        if cache_info:
            return jsonify({
                'success': True,
                'cache_info': cache_info,
                'is_valid': cache.is_cache_valid(country_code)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'キャッシュ情報が見つかりません'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/cache/data-freshness')
def get_data_freshness():
    """データ更新情報タブ用の統一的キャッシュ情報を取得"""
    try:
        freshness_info = {}
        
        # 各カテゴリのキャッシュ情報を取得
        categories = [
            ('JP', 'Google Trends'),
            ('JP', 'YouTube'),  # YouTubeもJPキーを使用
            ('spotify', 'Spotify'),
            ('news', 'World News'),
            ('podcast', 'Podcast'),
            ('rakuten', '楽天'),
            ('hatena', 'はてなブックマーク'),
            ('twitch', 'Twitch')
        ]
        
        for cache_key, display_name in categories:
            try:
                cache_info = cache.get_cache_info(cache_key)
                if cache_info:
                    freshness_info[display_name] = {
                        'last_updated': cache_info.get('last_updated'),
                        'data_count': cache_info.get('data_count'),
                        'status': '取得済み'
                    }
                else:
                    freshness_info[display_name] = {
                        'last_updated': None,
                        'data_count': 0,
                        'status': 'データなし'
                    }
            except Exception as e:
                freshness_info[display_name] = {
                    'last_updated': None,
                    'data_count': 0,
                    'status': f'エラー: {str(e)}'
                }
        
        return jsonify({
            'success': True,
            'data': freshness_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test-youtube')
def test_youtube():
    """YouTube APIのテスト用エンドポイント"""
    print("=== YouTube API テスト開始 ===")
    
    try:
        # YouTube Data APIキーの確認
        if not YOUTUBE_API_KEY:
            print("❌ YouTube APIキーが設定されていません")
        return jsonify({'error': 'YouTube APIキーが設定されていません'})
        
        print(f"✅ YouTube APIキー: {YOUTUBE_API_KEY[:10]}...")
        
        # YouTube Data APIクライアントの初期化
        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        print("✅ YouTube Data APIクライアント初期化成功")
        
        # 簡単なAPI呼び出しテスト
        request = youtube.videos().list(
            part='snippet',
            chart='mostPopular',
            regionCode='JP',
            maxResults=1
        )
        
        print("✅ YouTube API リクエスト作成成功")
        
        response = request.execute()
        print(f"✅ YouTube API レスポンス受信: {len(response.get('items', []))}件")
        
        return jsonify({
            'status': 'success',
            'message': 'YouTube API接続テスト成功',
            'data_count': len(response.get('items', []))
        })
        
    except Exception as e:
        print(f"❌ YouTube API テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/test-cache')
def test_cache():
    """キャッシュ機能のテスト用エンドポイント"""
    print("=== キャッシュ機能テスト開始 ===")
    
    try:
        # データベース接続テスト
        print("データベース接続テスト開始")
        
        # YouTubeキャッシュテーブルの存在確認
        with cache.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'youtube_trends_cache'
                    )
                """)
                table_exists = cursor.fetchone()[0]
                print(f"YouTubeキャッシュテーブル存在: {table_exists}")
                
                if table_exists:
                    # テーブル構造の確認
                    cursor.execute("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = 'youtube_trends_cache'
                        ORDER BY ordinal_position
                    """)
                    columns = cursor.fetchall()
                print(f"テーブル構造: {columns}")
        
        return jsonify({
            'status': 'success',
            'message': 'キャッシュ機能テスト成功',
            'table_exists': table_exists,
            'columns': columns if 'columns' in locals() else []
        })
        
    except Exception as e:
        print(f"❌ キャッシュ機能テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/news-trends')
def get_news_trends():
    """ニューストレンドデータを取得するAPIエンドポイント"""
    country = request.args.get('country', 'jp')
    category = request.args.get('category', 'general')
    
    try:
        print(f"=== News API 呼び出し開始 ===")
        print(f"リクエストパラメータ: country={country}, category={category}")
        
        # ニューストレンドを取得
        result = news_manager.get_trends(country, category)
        
        if 'error' in result:
            print(f"❌ News API エラー: {result['error']}")
        return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        print(f"✅ News API 成功: {result['status']} - {len(result['data'])}件")
        
        return jsonify({
            'success': True,
            'data': result['data'],
            'status': result['status'],
            'country': result['country'],
            'category': result['category']
        })
        
    except Exception as e:
        print(f"❌ News API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'ニューストレンドの取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/worldnews-trends')
def get_worldnews_trends():
    """World News APIから日本のニューストレンドデータを取得するAPIエンドポイント"""
    country = request.args.get('country', 'jp')
    category = request.args.get('category', 'general')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    # データベースのカテゴリ名に合わせる
    if category == 'general':
        category = 'worldnews_jp_general'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 World News Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_news_trends_cache(country, category)
                print(f"✅ World News Trends 古いキャッシュデータを削除しました")
        print(f"=== World News API 呼び出し開始 ===")
        print(f"リクエストパラメータ: country={country}, category={category}")
        
        # World News Trends Managerを使用してデータを取得
        print("World News Trends Managerを使用してデータを取得します")
        if worldnews_manager:
            result = worldnews_manager.get_trends(country, 'general', force_refresh=force_refresh)
            print(f"World News Manager結果タイプ: {type(result)}")
            
            if isinstance(result, dict):
                if result.get('error'):
                    print(f"World News Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'country': country,
                        'category': category
                    })
                elif result.get('data'):
                    print(f"World News Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'unknown'),
                        'country': country,
                        'category': category,
                        'data': result['data'],
                        'source': 'World News API',
                        'cache_info': result.get('cache_info')
                    })
                else:
                    print("World News Managerからデータを取得できませんでした")
        return jsonify({
            'success': False,
                        'error': 'World News Managerからデータを取得できませんでした',
                        'country': country,
                        'category': category
                    })
            else:
                print(f"World News Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'World News Manager予期しない戻り値タイプ: {type(result)}',
                    'country': country,
                    'category': category
                })
        else:
            return jsonify({
                'success': False,
                'error': 'World News Managerが初期化されていません',
                'country': country,
                'category': category
            })
        
    except Exception as e:
        print(f"❌ World News API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'World News APIからのニューストレンド取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/podcast-trends')
def get_podcast_trends():
    """Podcast トレンドを取得するAPI"""
    trend_type = request.args.get('trend_type', 'program')
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 Podcast Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_podcast_trends_cache(trend_type)
                print(f"✅ Podcast Trends 古いキャッシュデータを削除しました")
        print(f"=== Podcast API 呼び出し開始 ===")
        print(f"リクエストパラメータ: trend_type={trend_type}")
        
        # Podcast Trends Managerを使用してデータを取得
        print("Podcast Trends Managerを使用してデータを取得します")
        
        # trend_typeをPodcast Managerが理解する形式に変換
            if trend_type == 'program':
            manager_trend_type = 'best_podcasts'
            else:
            manager_trend_type = trend_type
            
        if podcast_manager:
            result = podcast_manager.get_trends(manager_trend_type)
            print(f"Podcast Manager結果タイプ: {type(result)}")
            
            if isinstance(result, dict):
                if result.get('error'):
                    print(f"Podcast Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'trend_type': trend_type
                    })
                elif result.get('data'):
                    print(f"Podcast Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'unknown'),
                        'trend_type': trend_type,
                        'data': result['data'],
                        'source': 'Podcast API',
                        'cache_info': result.get('cache_info')
                    })
                else:
                    print("Podcast Managerからデータを取得できませんでした")
        return jsonify({
            'success': False,
                        'error': 'Podcast Managerからデータを取得できませんでした',
                        'trend_type': trend_type
                    })
            else:
                print(f"Podcast Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'Podcast Manager予期しない戻り値タイプ: {type(result)}',
                    'trend_type': trend_type
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Podcast Managerが初期化されていません',
                'trend_type': trend_type
            })
            
    except Exception as e:
        print(f"❌ Podcast API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Podcast トレンドの取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/rakuten-trends')
def get_rakuten_trends():
    """楽天商品トレンドを取得するAPIエンドポイント"""
    genre_id = request.args.get('genre_id', None)
    limit = int(request.args.get('limit', 25))
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 Rakuten Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_rakuten_trends_cache(genre_id)
                print(f"✅ Rakuten Trends 古いキャッシュデータを削除しました")
        print(f"=== Rakuten API 呼び出し開始 ===")
        print(f"リクエストパラメータ: genre_id={genre_id}, limit={limit}")
        
        # Rakuten Trends Managerを使用してデータを取得
        print("Rakuten Trends Managerを使用してデータを取得します")
        if rakuten_manager:
            result = rakuten_manager.get_trends(genre_id, limit, force_refresh)
            print(f"Rakuten Manager結果タイプ: {type(result)}")
            
            if isinstance(result, dict):
                if result.get('error'):
                    print(f"Rakuten Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'genre_id': genre_id
                    })
                elif result.get('data'):
                    print(f"Rakuten Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'fresh'),
                        'genre_id': genre_id,
                        'data': result['data'],
                        'source': '楽天商品ランキング',
                        'total_count': len(result['data']),
                        'cache_info': result.get('cache_info')
                    })
                else:
                    print("Rakuten Managerからデータを取得できませんでした")
        return jsonify({
            'success': False,
                        'error': 'Rakuten Managerからデータを取得できませんでした',
                        'genre_id': genre_id
                    })
            else:
                print(f"Rakuten Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'Rakuten Manager予期しない戻り値タイプ: {type(result)}',
                    'genre_id': genre_id
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Rakuten Managerが初期化されていません',
                'genre_id': genre_id
            })
        
    except Exception as e:
        print(f"❌ Rakuten API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'楽天商品トレンドの取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/rakuten-genres')
def get_rakuten_genres():
    """楽天ジャンル一覧を取得するAPIエンドポイント"""
    try:
        print(f"=== Rakuten Genres API 呼び出し開始 ===")
        
        # 楽天ジャンル一覧を取得
        result = rakuten_manager.get_genres()
        
        if 'error' in result:
            print(f"❌ Rakuten Genres API エラー: {result['error']}")
        return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        print(f"✅ Rakuten Genres API 成功: {len(result['data'])}件")
        
        return jsonify({
            'success': True,
            'data': result['data'],
            'status': result['status'],
            'source': result['source']
        })
        
    except Exception as e:
        print(f"❌ Rakuten Genres API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'楽天ジャンル一覧の取得に失敗しました: {str(e)}'
        }), 500

# @app.route('/api/reddit-trends')  # ファイルが削除されたため無効化
# def get_reddit_trends():
#     """Redditトレンドを取得するAPIエンドポイント"""
#     return jsonify({
#         'success': False,
#         'error': 'Redditトレンド機能は無効化されています'
#     }), 503

# @app.route('/api/reddit-subreddits')  # ファイルが削除されたため無効化
# def get_reddit_subreddits():
#     """Reddit人気サブレディットを取得するAPIエンドポイント"""
#     return jsonify({
#         'success': False,
#         'error': 'Reddit機能は無効化されています'
#     }), 503

@app.route('/api/hatena-trends')
def get_hatena_trends():
    """はてなブックマークトレンドを取得するAPIエンドポイント"""
    category = request.args.get('category', 'all')
    limit = int(request.args.get('limit', 25))
    entry_type = request.args.get('type', 'hot')  # hot or new
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 Hatena Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_hatena_trends_cache(category, entry_type)
                print(f"✅ Hatena Trends 古いキャッシュデータを削除しました")
        print(f"=== はてなブックマーク API 呼び出し開始 ===")
        print(f"リクエストパラメータ: category={category}, limit={limit}, type={entry_type}")
        
        # はてなブックマーク Trends Managerを使用してデータを取得
        print("はてなブックマーク Trends Managerを使用してデータを取得します")
        if hatena_manager:
            result = hatena_manager.get_trends(category, limit, force_refresh)
            print(f"はてなブックマーク Manager結果タイプ: {type(result)}")
            
            if isinstance(result, dict):
                if result.get('error'):
                    print(f"はてなブックマーク Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'category': category,
                        'entry_type': entry_type
                    })
                elif result.get('data'):
                    print(f"はてなブックマーク Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'fresh'),
                        'category': category,
                        'entry_type': entry_type,
                        'data': result['data'],
                        'source': 'はてなブックマークホットエントリー',
                        'total_count': len(result['data']),
                        'cache_info': result.get('cache_info')
                    })
                else:
                    print("はてなブックマーク Managerからデータを取得できませんでした")
        return jsonify({
                'success': False,
                        'error': 'はてなブックマーク Managerからデータを取得できませんでした',
                        'category': category,
                        'entry_type': entry_type
                    })
            elif isinstance(result, list):
                print(f"はてなブックマーク Managerからリスト形式で{len(result)}件のデータを取得しました")
                return jsonify({
                    'success': True,
                    'status': 'fresh',
                    'category': category,
                    'entry_type': entry_type,
                    'data': result,
                    'source': 'はてなブックマークホットエントリー',
                    'total_count': len(result),
                    'cache_info': {'last_updated': None, 'data_count': len(result)}
                })
            else:
                print(f"はてなブックマーク Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'はてなブックマーク Manager予期しない戻り値タイプ: {type(result)}',
                    'category': category,
                    'entry_type': entry_type
                })
        else:
            return jsonify({
                'success': False,
                'error': 'はてなブックマーク Managerが初期化されていません',
                'category': category,
                'entry_type': entry_type
            })
        
    except Exception as e:
        print(f"❌ はてなブックマーク API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'はてなブックマークトレンドの取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/hatena-categories')
def get_hatena_categories():
    """はてなブックマークカテゴリー一覧を取得するAPIエンドポイント"""
    try:
        print(f"=== はてなブックマークカテゴリー API 呼び出し開始 ===")
        
        # はてなブックマークカテゴリー一覧を取得
        categories = hatena_manager.get_available_categories()
        
        print(f"✅ はてなブックマークカテゴリー API 成功: {len(categories)}件")
        
        return jsonify({
            'success': True,
            'data': categories,
            'status': 'success',
            'source': 'はてなブックマークカテゴリー一覧'
        })
        
    except Exception as e:
        print(f"❌ はてなブックマークカテゴリー API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'はてなブックマークカテゴリー一覧の取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/twitch-trends')
def get_twitch_trends():
    """Twitchトレンドを取得するAPIエンドポイント"""
    trend_type = request.args.get('type', 'games')  # games, streams, clips
    limit = int(request.args.get('limit', 25))
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
    # force_refresh=trueの場合、古いキャッシュデータを削除
        if force_refresh:
            print(f"🔄 Twitch Trends 強制更新: 古いキャッシュデータを削除します")
            cache = init_cache()
            if cache:
                cache.clear_twitch_trends_cache(trend_type)
                print(f"✅ Twitch Trends 古いキャッシュデータを削除しました")
        print(f"=== Twitch API 呼び出し開始 ===")
        print(f"リクエストパラメータ: type={trend_type}, limit={limit}")
        
        # Twitch Trends Managerを使用してデータを取得
        print("Twitch Trends Managerを使用してデータを取得します")
        if twitch_manager:
            if trend_type == 'games':
                result = twitch_manager.get_trends(limit, force_refresh)
            else:
                result = {'error': f'サポートされていないTwitchトレンドタイプ: {trend_type}'}
                
            print(f"Twitch Manager結果タイプ: {type(result)}")
            
            if isinstance(result, dict):
                if result.get('error'):
                    print(f"Twitch Manager エラー: {result.get('error')}")
                    return jsonify({
                        'success': False,
                        'error': result.get('error'),
                        'trend_type': trend_type
                    })
                elif result.get('data'):
                    print(f"Twitch Managerから{len(result['data'])}件のデータを取得しました")
                    return jsonify({
                        'success': True,
                        'status': result.get('status', 'fresh'),
                        'trend_type': trend_type,
                        'data': result['data'],
                        'source': 'Twitch 人気ゲーム',
                        'total_count': len(result['data']),
                        'cache_info': result.get('cache_info')
                    })
            else:
                    print("Twitch Managerからデータを取得できませんでした")
        return jsonify({
                'success': False,
                        'error': 'Twitch Managerからデータを取得できませんでした',
                        'trend_type': trend_type
                    })
            else:
                print(f"Twitch Manager予期しない戻り値タイプ: {type(result)}")
                return jsonify({
                    'success': False,
                    'error': f'Twitch Manager予期しない戻り値タイプ: {type(result)}',
                    'trend_type': trend_type
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Twitch Managerが初期化されていません',
                'trend_type': trend_type
            })
        
    except Exception as e:
        print(f"❌ Twitch API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Twitchトレンドの取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/twitch-japanese-streams')
def get_twitch_japanese_streams():
    """日本語Twitchストリームを取得するAPIエンドポイント"""
    limit = int(request.args.get('limit', 25))
    
    try:
        print(f"=== Twitch 日本語ストリーム API 呼び出し開始 ===")
        print(f"リクエストパラメータ: limit={limit}")
        
        # 日本語ストリームを取得
        result = twitch_manager.get_japanese_streams(limit)
        
        if 'error' in result:
            print(f"❌ Twitch 日本語ストリーム API エラー: {result['error']}")
        return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        print(f"✅ Twitch 日本語ストリーム API 成功: {result['status']} - {len(result['data'])}件")
        
        return jsonify({
            'success': True,
            'data': result['data'],
            'status': result['status'],
            'source': 'Twitch 日本語ストリーム',
            'total_count': result.get('total_count', 0)
        })
        
    except Exception as e:
        print(f"❌ Twitch 日本語ストリーム API 呼び出しエラー: {e}")
        return jsonify({
            'success': False,
            'error': f'Twitch 日本語ストリーム API 呼び出しエラー: {str(e)}'
        }), 500

@app.route('/api/twitch-categories')
def get_twitch_categories():
    """Twitchゲームカテゴリー一覧を取得するAPIエンドポイント"""
    try:
        print(f"=== Twitch カテゴリー API 呼び出し開始 ===")
        
        # Twitchゲームカテゴリー一覧を取得
        categories = twitch_manager.get_game_categories()
        
        print(f"✅ Twitch カテゴリー API 成功: {len(categories)}件")
        
        return jsonify({
            'success': True,
            'data': categories,
            'status': 'success',
            'source': 'Twitch ゲームカテゴリー一覧'
        })
        
    except Exception as e:
        print(f"❌ Twitch カテゴリー API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Twitchゲームカテゴリー一覧の取得に失敗しました: {str(e)}'
        }), 500

@app.route('/api/scheduler-status')
def get_scheduler_status():
    """スケジューラーの状態を取得するAPIエンドポイント"""
    try:
        status = scheduler.get_status()
        return jsonify({
            'success': True,
            'data': status,
            'message': 'スケジューラー状態取得完了'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'スケジューラー状態取得エラー: {str(e)}'
        }), 500

@app.route('/api/trigger-fetch', methods=['POST'])
def trigger_manual_fetch():
    """手動で全トレンド取得を実行するAPIエンドポイント"""
    try:
        print("🔄 手動トレンド取得開始")
        scheduler._fetch_all_trends()
        return jsonify({
            'success': True,
            'message': '手動トレンド取得完了'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'手動トレンド取得エラー: {str(e)}'
        }), 500

@app.route('/api/cleanup-old-data')
def cleanup_old_data():
    """古いデータをクリーンアップするAPIエンドポイント"""
    try:
        from database_config import TrendsCache
        db = TrendsCache()
        
        # YouTube (US)の古いデータを削除
        deleted_count = db.cleanup_old_youtube_us_data()
        
        return jsonify({
            'success': True,
            'message': f'{deleted_count}件の古いデータを削除しました',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'クリーンアップエラー: {str(e)}'
        }), 500

@app.route('/api/cached-data')
def get_cached_data():
    """キャッシュされた全プラットフォームのデータを一括取得するAPIエンドポイント"""
    try:
        from database_config import TrendsCache
        from datetime import datetime
        
        db = TrendsCache()
        
        # 最新のスケジューラートレンドデータを取得
        latest_trends = db.get_latest_scheduler_trends(limit=10)
        
        if not latest_trends:
            return jsonify({
                'success': False,
                'error': 'キャッシュデータが見つかりません'
            })
        
        # プラットフォーム別にデータを整理
        cached_data = {}
        for trend in latest_trends:
            platform = trend['platform']
            trend_type = trend['trend_type']
            
            # プラットフォーム名を統一
            if platform == 'Google Trends':
                cached_data['google_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'YouTube':
                if trend_type == 'JP':
                    cached_data['youtube_trends'] = {
                        'success': True,
                        'data': trend['data'],
                        'status': 'cached',
                        'region_code': 'JP',
                        'source': 'database_cache',
                        'created_at': trend['created_at']
                    }
            elif platform == 'Spotify':
                cached_data['music_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'World News':
                cached_data['world_news'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'Podcast':
                cached_data['podcast_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'Hatena':
                cached_data['hatena_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'Twitch':
                cached_data['twitch_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
            elif platform == 'Rakuten':
                cached_data['rakuten_trends'] = {
                    'success': True,
                    'data': trend['data'],
                    'status': 'cached',
                    'source': 'database_cache',
                    'created_at': trend['created_at']
                }
        
        return jsonify({
            'success': True,
            'data': cached_data,
            'message': f'{len(cached_data)}プラットフォームのキャッシュデータを取得しました'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'キャッシュデータ取得に失敗しました: {str(e)}'
        }), 500


# スケジューラーのインポートと初期化
try:
from scheduler_manager import TrendsScheduler
# スケジューラーのインスタンスを作成
scheduler = TrendsScheduler(app)
    print("✅ スケジューラー初期化完了")
except Exception as e:
    print(f"❌ スケジューラー初期化エラー: {e}")
    scheduler = None


if __name__ == '__main__':
    try:
        # スケジューラーを開始
        if scheduler:
        scheduler.start()
        print("🚀 スケジューラー開始完了")
            print("📅 毎日朝5:00に全トレンドを自動取得します")
        else:
            print("⚠️ スケジューラーは無効です")
        
        # Flaskアプリを開始
        port = int(os.getenv('FLASK_PORT', 5001))
        print(f"🚀 アプリケーションをポート {port} で起動します")
        app.run(debug=True, host='0.0.0.0', port=port)
        
    except KeyboardInterrupt:
        print("\n🛑 アプリケーション終了中...")
        if scheduler:
        scheduler.stop()
        print("✅ スケジューラー停止完了")
    except Exception as e:
        print(f"❌ アプリケーション起動エラー: {e}")
        if scheduler:
        scheduler.stop()