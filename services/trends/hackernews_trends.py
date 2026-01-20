import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class HackerNewsTrendsManager(BaseTrendsManager):
    """Hacker Newsのトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='hackernews', max_requests=30, window_seconds=60)
        
        self.base_url = "https://hacker-news.firebaseio.com/v0"
        
        logger.info(f"Hacker News Trends Manager初期化:")
        logger.info(f"  Base URL: {self.base_url}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'hackernews_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        story_type = kwargs.get('story_type', 'top')
        return self.db.get_hackernews_trends_from_cache(story_type)

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            story_type = kwargs.get('story_type', 'top')
            return self.db.save_hackernews_trends_to_cache(data, story_type)
        except Exception as e:
            logger.error(f"❌ Hacker News キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            story_type = kwargs.get('story_type', 'top')
            return self.db.clear_hackernews_trends_cache(story_type)
        except Exception as e:
            logger.error(f"❌ Hacker News キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ Hacker News: cache_status更新エラー: {e}")
            return False

    def get_trends(self, story_type='top', limit=25, force_refresh=False):
        """Hacker Newsトレンドを取得（キャッシュ優先、scoreでソート）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Trueで、キャッシュがない場合はAPIを呼び出す
        # sort_key='score'でスコアでソート
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=True,  # キャッシュがない場合はAPIを呼び出す
            sort_key='score',  # スコアでソート
            sort_reverse=True,  # 降順
            story_type=story_type
        )
        # story_typeパラメータを結果に追加
        if result and isinstance(result, dict):
            result['story_type'] = story_type
        return result
    
    def get_top_stories(self, story_type='top', limit=25):
        """Hacker Newsのトップストーリーを取得（既存APIとの互換性のため）"""
        # force_refresh=Trueで強制更新
        return self.get_trends(story_type=story_type, limit=limit, force_refresh=True)
    
    def _fetch_trends(self, story_type='top', limit=25, *args, **kwargs):
        """Hacker Newsのトップストーリーを取得"""
        try:
            logger.info(f"Hacker News API呼び出し開始 (type: {story_type}, limit: {limit})")
            
            # ストーリーIDのリストを取得
            story_list_url = f"{self.base_url}/{story_type}stories.json"
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            response = requests.get(story_list_url, timeout=10)
            
            if response.status_code != 200:
                return {
                    'error': f'Hacker News API エラー: {response.status_code}',
                    'success': False
                }
            
            story_ids = response.json()[:limit]
            logger.debug(f"取得したストーリーID数: {len(story_ids)}")
            
            # 各ストーリーの詳細を取得
            stories = []
            for story_id in story_ids:
                try:
                    story_url = f"{self.base_url}/item/{story_id}.json"
                    # レート制限をチェック（各ストーリー取得前に）
                    self.rate_limiter.wait_if_needed()
                    
                    story_response = requests.get(story_url, timeout=5)
                    
                    if story_response.status_code == 200:
                        story_data = story_response.json()
                        
                        # ストーリー情報を整形
                        stories.append({
                            'story_id': story_id,
                            'title': story_data.get('title', 'No Title'),
                            'url': story_data.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
                            'score': story_data.get('score', 0),
                            'by': story_data.get('by', 'Unknown'),
                            'time': story_data.get('time', 0),
                            'comments': story_data.get('descendants', 0),
                            'type': story_data.get('type', 'story'),
                            'story_type': story_type
                        })
                        
                except Exception as e:
                    logger.warning(f"ストーリー {story_id} 取得エラー: {e}", exc_info=True)
                    continue
            
            # スコアでソート（降順）
            stories.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # ランキングを設定
            for i, story in enumerate(stories, 1):
                story['rank'] = i
            
            logger.info(f"✅ Hacker News: {len(stories)}件のストーリーを取得し、スコアでソートしました")
            
            return {
                'success': True,
                'data': stories,
                'status': 'api_fetched',
                'source': 'Hacker News API',
                'story_type': story_type,
                'total_count': len(stories)
            }
            
        except Exception as e:
            logger.error(f"❌ Hacker News API エラー: {e}", exc_info=True)
            return {
                'error': f'Hacker Newsストーリー取得エラー: {str(e)}',
                'success': False
            }
