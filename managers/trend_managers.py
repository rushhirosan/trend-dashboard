"""
トレンドマネージャーの初期化
各トレンドマネージャーのインスタンスを作成・管理
"""

from services.trends.google_trends import GoogleTrendsManager
from services.trends.youtube_trends import YouTubeTrendsManager
from services.trends.music_trends import MusicTrendsManager
from services.trends.news_trends import NewsTrendsManager
from services.trends.worldnews_trends import WorldNewsTrendsManager
from services.trends.podcast_trends import PodcastTrendsManager
from services.trends.rakuten_trends import RakutenTrendsManager
from services.trends.hatena_trends import HatenaTrendsManager
from services.trends.twitch_trends import TwitchTrendsManager


def initialize_managers():
    """
    全トレンドマネージャーを初期化
    
    Returns:
        dict: 初期化されたマネージャーの辞書
    """
    managers = {}
    
    # Google Trends管理インスタンスを作成
    try:
        managers['google'] = GoogleTrendsManager()
        print("✅ Google Trends Manager初期化完了")
    except Exception as e:
        print(f"❌ Google Trends Manager初期化エラー: {e}")
        managers['google'] = None
    
    # YouTube Trends管理インスタンスを作成
    try:
        managers['youtube'] = YouTubeTrendsManager()
        print("✅ YouTube Manager初期化完了")
    except Exception as e:
        print(f"❌ YouTube Manager初期化エラー: {e}")
        managers['youtube'] = None

    # 音楽トレンド Manager
    try:
        managers['music'] = MusicTrendsManager()
        print("✅ Music Manager初期化完了")
    except Exception as e:
        print(f"❌ Music Manager初期化エラー: {e}")
        managers['music'] = None

    # ニューストレンド Manager
    try:
        managers['news'] = NewsTrendsManager()
        print("✅ News Manager初期化完了")
    except Exception as e:
        print(f"❌ News Manager初期化エラー: {e}")
        managers['news'] = None

    # World News API Manager
    try:
        managers['worldnews'] = WorldNewsTrendsManager()
        print("✅ World News Manager初期化完了")
    except Exception as e:
        print(f"❌ World News Manager初期化エラー: {e}")
        managers['worldnews'] = None

    # ポッドキャストトレンド Manager
    try:
        managers['podcast'] = PodcastTrendsManager()
        print("✅ Podcast Manager初期化完了")
    except Exception as e:
        print(f"❌ Podcast Manager初期化エラー: {e}")
        managers['podcast'] = None

    # 楽天トレンド Manager
    try:
        managers['rakuten'] = RakutenTrendsManager()
        print("✅ Rakuten Manager初期化完了")
    except Exception as e:
        print(f"❌ Rakuten Manager初期化エラー: {e}")
        managers['rakuten'] = None

    # はてなブックマークトレンド Manager
    try:
        managers['hatena'] = HatenaTrendsManager()
        print("✅ Hatena Manager初期化完了")
    except Exception as e:
        print(f"❌ Hatena Manager初期化エラー: {e}")
        managers['hatena'] = None

    # Twitchトレンド Manager
    try:
        managers['twitch'] = TwitchTrendsManager()
        print("✅ Twitch Manager初期化完了")
    except Exception as e:
        print(f"❌ Twitch Manager初期化エラー: {e}")
        managers['twitch'] = None

    return managers

