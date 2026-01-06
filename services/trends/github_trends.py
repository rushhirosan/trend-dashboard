import os
import requests
import time
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

# ロガーの初期化
logger = get_logger(__name__)

class GitHubTrendsManager:
    """GitHubトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.base_url = "https://api.github.com"
        # GitHub APIの認証トークン（オプション、レート制限緩和のため）
        self.access_token = os.getenv('GITHUB_ACCESS_TOKEN')
        
        self.db = TrendsCache()
        # レート制限: 認証なしは1時間60回、認証ありは1時間5000回
        self.rate_limiter = get_rate_limiter('github', max_requests=10, window_seconds=60)
        
        logger.info(f"GitHub Trends Manager初期化:")
        logger.info(f"  API URL: {self.base_url}")
        logger.info(f"  Access Token: {'設定済み' if self.access_token else '未設定（認証なし、1時間60回制限）'}")
    
    def get_trends(self, language='all', limit=25, force_refresh=False):
        """GitHubトレンドを取得（キャッシュ優先）"""
        try:
            if force_refresh:
                logger.info(f"🔄 GitHub force_refresh: キャッシュをクリアします")
                self.db.clear_github_trends_cache()
            
            # キャッシュからデータを取得
            cached_data = self.db.get_github_trends_from_cache()
            
            if cached_data:
                logger.info(f"✅ GitHub: キャッシュから{len(cached_data)}件のデータを取得しました")
                # cache_statusを更新
                self.db.update_cache_status('github_trends', len(cached_data))
                return {
                    'success': True,
                    'data': cached_data,
                    'status': 'cached',
                    'source': 'database_cache',
                    'language': language
                }
            else:
                # force_refresh=Falseの場合は、キャッシュがない場合でも外部APIを呼び出さない
                if not force_refresh:
                    logger.warning("⚠️ GitHub: キャッシュにデータがありませんが、force_refresh=falseのため外部APIは呼び出しません")
                    return {
                        'success': True,  # エラーではなく、データがない状態として扱う
                        'data': [],
                        'status': 'cache_not_found',
                        'source': 'database_cache',
                        'language': language
                    }
                # force_refresh=trueの場合のみ外部APIを呼び出す
                logger.warning("⚠️ GitHub: キャッシュデータが見つかりません。外部APIを呼び出します")
                return self.get_trending_repositories(language, limit)
                
        except Exception as e:
            logger.error(f"❌ GitHub トレンド取得エラー: {e}", exc_info=True)
            return {'error': f'GitHubトレンドの取得に失敗しました: {str(e)}', 'success': False}
    
    def get_trending_repositories(self, language='all', limit=25):
        """GitHubの人気リポジトリを取得"""
        try:
            # レート制限をチェック
            self.rate_limiter.wait_if_needed()
            
            # GitHub Search APIを使用してスター数が多いリポジトリを取得
            url = f"{self.base_url}/search/repositories"
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Trend-Dashboard'
            }
            
            # 認証トークンが設定されている場合は追加
            if self.access_token:
                headers['Authorization'] = f'token {self.access_token}'
            
            # クエリパラメータ: 過去1週間でスターが多く、言語でフィルタ
            query = f"stars:>1000"
            if language and language != 'all':
                query += f" language:{language}"
            
            params = {
                'q': query,
                'sort': 'stars',
                'order': 'desc',
                'per_page': min(limit, 100)  # GitHubの最大制限は100
            }
            
            logger.debug(f"GitHub API呼び出し: {url}")
            logger.debug(f"GitHub API パラメータ: {params}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            logger.debug(f"GitHub APIレスポンス: status={response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                logger.error(f"GitHub APIエラーレスポンス: {error_text}")
                return {
                    'error': f'GitHub API エラー: {response.status_code}',
                    'success': False,
                    'status_code': response.status_code,
                    'response_text': error_text
                }
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                # データを整形
                formatted_data = []
                for i, item in enumerate(items[:limit], 1):
                    formatted_item = {
                        'repo_id': str(item.get('id', '')),
                        'name': item.get('name', ''),
                        'full_name': item.get('full_name', ''),
                        'description': item.get('description', ''),
                        'url': item.get('html_url', ''),
                        'language': item.get('language', ''),
                        'stars_count': item.get('stargazers_count', 0),
                        'forks_count': item.get('forks_count', 0),
                        'watchers_count': item.get('watchers_count', 0),
                        'open_issues_count': item.get('open_issues_count', 0),
                        'created_at': item.get('created_at', ''),
                        'updated_at': item.get('updated_at', ''),
                        'pushed_at': item.get('pushed_at', ''),
                        'owner_login': item.get('owner', {}).get('login', ''),
                        'owner_avatar_url': item.get('owner', {}).get('avatar_url', ''),
                        'rank': i
                    }
                    formatted_data.append(formatted_item)
                
                # データベースにキャッシュ
                if formatted_data:
                    self.db.save_github_trends_to_cache(formatted_data)
                    # cache_statusを更新
                    self.db.update_cache_status('github_trends', len(formatted_data))
                
                logger.info(f"✅ GitHub: {len(formatted_data)}件のトレンドリポジトリを取得しました")
                return {
                    'success': True,
                    'data': formatted_data,
                    'status': 'api_fetched',
                    'source': 'github_api',
                    'language': language
                }
            else:
                return {
                    'error': f'GitHub API 予期しないレスポンス: {response.status_code}',
                    'success': False
                }
                
        except requests.exceptions.Timeout:
            logger.error("❌ GitHub API タイムアウトエラー")
            return {
                'error': 'GitHub API タイムアウト',
                'success': False
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ GitHub API リクエストエラー: {e}", exc_info=True)
            return {
                'error': f'GitHub API リクエストエラー: {str(e)}',
                'success': False
            }
        except Exception as e:
            logger.error(f"❌ GitHub トレンド取得エラー: {e}", exc_info=True)
            return {
                'error': f'GitHubトレンドの取得に失敗しました: {str(e)}',
                'success': False
            }

