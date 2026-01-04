import requests
from datetime import datetime
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class HackerNewsTrendsManager:
    """Hacker Newsのトレンドを取得・管理するクラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://hacker-news.firebaseio.com/v0"
        self.db = TrendsCache()
        # レート制限: Hacker News APIは特に制限なしだが、保守的に10リクエスト/分に設定
        self.rate_limiter = get_rate_limiter('hackernews', max_requests=10, window_seconds=60)
        
        logger.info(f"Hacker News Trends Manager初期化:")
        logger.info(f"  Base URL: {self.base_url}")
    
    def get_trends(self, story_type='top', limit=25, force_refresh=False):
        """Hacker Newsトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 Hacker News force_refresh: キャッシュをクリアします")
                self.db.clear_hackernews_trends_cache(story_type)
            
            # キャッシュからデータを取得
            cached_data = self.db.get_hackernews_trends_from_cache(story_type)
            
            if cached_data:
                # スコアでソート（降順）
                cached_data.sort(key=lambda x: x.get('score', 0), reverse=True)
                
                # ランキングを再設定
                for i, item in enumerate(cached_data, 1):
                    item['rank'] = i
                
                # キャッシュデータを使用する場合でも、cache_statusを更新（スケジューラー実行時の時刻を統一するため）
                if force_refresh:
                    try:
                        self.db.update_cache_status('hackernews_trends', len(cached_data))
                    except Exception as e:
                        logger.warning(f"⚠️ Hacker News: cache_status更新エラー（処理は継続）: {e}")
                
                logger.info(f"✅ Hacker News: キャッシュから{len(cached_data)}件のデータを取得し、スコアでソートしました")
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'story_type': story_type
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ Hacker News: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': False,
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'story_type': story_type,
                        'error': 'キャッシュにデータがありません'
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ Hacker News: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self.get_top_stories(story_type, limit)
                
        except Exception as e:
            logger.error(f"❌ Hacker News トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'Hacker Newsトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def get_top_stories(self, story_type='top', limit=25):
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
            
            # キャッシュに保存
            self.db.save_hackernews_trends_to_cache(stories, story_type)
            
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




