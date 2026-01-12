import os
import requests
import time
from datetime import datetime, timedelta
from database_config import TrendsCache
from utils.logger_config import get_logger
from services.trends.base_trends_manager import BaseTrendsManager

# ロガーの初期化
logger = get_logger(__name__)

class GitHubTrendsManager(BaseTrendsManager):
    """GitHubトレンド管理クラス"""
    
    def __init__(self):
        """初期化"""
        # ベースクラスを初期化（rate_limiterも自動的に初期化される）
        super().__init__(service_name='github', max_requests=10, window_seconds=60)
        
        self.base_url = "https://api.github.com"
        # GitHub APIの認証トークン（オプション、レート制限緩和のため）
        self.access_token = os.getenv('GITHUB_ACCESS_TOKEN')
        
        logger.info(f"GitHub Trends Manager初期化:")
        logger.info(f"  API URL: {self.base_url}")
        logger.info(f"  Access Token: {'設定済み' if self.access_token else '未設定（認証なし、1時間60回制限）'}")
    
    def _get_cache_key(self):
        """キャッシュキーを返す"""
        return 'github_trends'

    def _get_from_cache(self, *args, **kwargs):
        """キャッシュからデータを取得"""
        return self.db.get_github_trends_from_cache()

    def _save_to_cache(self, data, *args, **kwargs):
        """キャッシュにデータを保存"""
        try:
            return self.db.save_github_trends_to_cache(data)
        except Exception as e:
            logger.error(f"❌ GitHub キャッシュ保存エラー: {e}", exc_info=True)
            return False

    def _clear_cache(self, *args, **kwargs):
        """キャッシュをクリア"""
        try:
            return self.db.clear_github_trends_cache()
        except Exception as e:
            logger.error(f"❌ GitHub キャッシュクリアエラー: {e}", exc_info=True)
            return False

    def _update_cache_status(self, cache_key, data_count):
        """cache_statusテーブルを更新"""
        try:
            return self.db.update_cache_status(cache_key, data_count)
        except Exception as e:
            logger.warning(f"⚠️ GitHub: cache_status更新エラー: {e}")
            return False

    def get_trends(self, language='all', limit=25, force_refresh=False):
        """GitHubトレンドを取得（キャッシュ優先）"""
        # ベースクラスのget_trendsを使用
        # auto_fetch_on_cache_miss=Falseで、既存動作を維持（キャッシュがない場合はAPIを呼び出さない）
        result = super().get_trends(
            limit=limit,
            force_refresh=force_refresh,
            auto_fetch_on_cache_miss=False,  # 既存動作を維持
            language=language
        )
        # languageパラメータを結果に追加
        if result and isinstance(result, dict):
            result['language'] = language
        return result
    
    def get_trending_repositories(self, language='all', limit=25):
        """GitHubの人気リポジトリを取得"""
        # このメソッドは既存のAPIとの互換性のために残すが、get_trendsに委譲
        return self.get_trends(language=language, limit=limit, force_refresh=True)
    
    def _fetch_trends(self, language='all', limit=25, *args, **kwargs):
        """GitHub Search APIからトレンドデータを取得"""
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
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            # レート制限情報をログに記録
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Remaining']
                limit_header = response.headers.get('X-RateLimit-Limit', '?')
                logger.debug(f"📊 GitHub API レート制限: 残り {remaining}/{limit_header}")
            
            logger.info(f"📊 GitHub API: HTTP status={response.status_code}")
            
            if response.status_code == 403:
                # レート制限エラー
                reset_time = response.headers.get('X-RateLimit-Reset')
                if reset_time:
                    reset_datetime = datetime.fromtimestamp(int(reset_time))
                    logger.warning(f"⚠️ GitHub API: レート制限に達しました。リセット時刻: {reset_datetime}")
                else:
                    logger.warning(f"⚠️ GitHub API: レート制限に達しました")
                return {
                    'success': False,
                    'data': [],
                    'status': 'rate_limit_exceeded',
                    'source': 'github_api',
                    'error': 'GitHub APIのレート制限に達しました'
                }
            
            if response.status_code != 200:
                logger.warning(f"⚠️ GitHub API: HTTP {response.status_code} - {response.text[:200]}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'api_fetch_failed',
                    'source': 'github_api',
                    'error': f'API取得に失敗しました: HTTP {response.status_code}'
                }
            
            data = response.json()
            repositories = data.get('items', [])
            
            if not repositories:
                logger.warning("⚠️ GitHub API: リポジトリが取得できませんでした")
                return {
                    'success': True,
                    'data': [],
                    'status': 'no_repositories',
                    'source': 'github_api'
                }
            
            # データを整形
            formatted_data = []
            for repo in repositories:
                try:
                    # 更新日時をパース
                    updated_at = repo.get('updated_at')
                    if updated_at:
                        try:
                            updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        except Exception:
                            updated_date = datetime.now()
                    else:
                        updated_date = datetime.now()
                    
                    # 作成日時をパース
                    created_at = repo.get('created_at')
                    created_date = None
                    if created_at:
                        try:
                            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        except Exception:
                            created_date = datetime.now()
                    
                    formatted_data.append({
                        'id': repo.get('id'),
                        'name': repo.get('name', ''),
                        'full_name': repo.get('full_name', ''),
                        'description': repo.get('description', '')[:300] if repo.get('description') else '',
                        'url': repo.get('html_url', ''),
                        'language': repo.get('language', ''),
                        'stars': repo.get('stargazers_count', 0),
                        'forks': repo.get('forks_count', 0),
                        'open_issues': repo.get('open_issues_count', 0),
                        'created_at': created_date.isoformat() if created_date else None,
                        'updated_at': updated_date.isoformat() if updated_date else None,
                        'owner': repo.get('owner', {}).get('login', '') if repo.get('owner') else '',
                        'source': 'GitHub'
                    })
                except Exception as e:
                    logger.warning(f"⚠️ GitHub リポジトリデータの処理でエラー: {e}", exc_info=True)
                    continue
            
            # starsでソート（降順）- 既にAPIでソート済みだが念のため
            formatted_data.sort(key=lambda x: x.get('stars', 0), reverse=True)
            
            # ランキングを設定
            for i, item in enumerate(formatted_data[:limit], 1):
                item['rank'] = i
            
            final_data = formatted_data[:limit]
            
            logger.info(f"✅ GitHub: {len(final_data)}件のリポジトリを取得しました")
            return {
                'success': True,
                'data': final_data,
                'status': 'api_fetched',
                'source': 'github_api',
                'language': language,
                'total_count': len(final_data)
            }
        except requests.exceptions.Timeout:
            logger.error("❌ GitHub API タイムアウトエラー", exc_info=True)
            return {'error': 'GitHub API タイムアウト', 'success': False}
        except Exception as e:
            logger.error(f"❌ GitHub API エラー: {e}", exc_info=True)
            return {'error': f'GitHub API取得エラー: {str(e)}', 'success': False}
