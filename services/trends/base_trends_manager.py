"""
トレンドマネージャーのベースクラス
共通の処理（rate_limiter初期化、キャッシュチェック、エラーハンドリング）を提供
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class BaseTrendsManager(ABC):
    """トレンドマネージャーのベースクラス
    
    共通の処理を提供し、各トレンドマネージャーは以下を実装する必要がある：
    - _fetch_trends(): 外部APIからデータを取得するメソッド
    - _get_cache_key(): キャッシュキーを返すメソッド（オプション、デフォルト実装あり）
    - _get_from_cache(): キャッシュからデータを取得するメソッド（オプション）
    - _save_to_cache(): キャッシュにデータを保存するメソッド（オプション）
    - _clear_cache(): キャッシュをクリアするメソッド（オプション）
    """
    
    def __init__(self, service_name: str, max_requests: int = 10, window_seconds: int = 60):
        """初期化
        
        Args:
            service_name: サービスの名前（rate_limiterのキーとして使用）
            max_requests: レート制限の最大リクエスト数
            window_seconds: レート制限の時間ウィンドウ（秒）
        """
        self.service_name = service_name
        self.db = TrendsCache()
        self.rate_limiter = get_rate_limiter(service_name, max_requests=max_requests, window_seconds=window_seconds)
        logger.debug(f"✅ {self.service_name}: BaseTrendsManager初期化完了 (rate_limiter: {max_requests}/{window_seconds}s)")
    
    @abstractmethod
    def _fetch_trends(self, *args, **kwargs) -> Dict[str, Any]:
        """外部APIからデータを取得するメソッド（各マネージャーで実装必須）
        
        Returns:
            Dict: {
                'success': bool,
                'data': List[Dict],
                'status': str,
                'source': str,
                ... その他のメタデータ
            }
        """
        pass
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """キャッシュキーを返す（オプション、デフォルト実装）
        
        各マネージャーで必要に応じてオーバーライド
        """
        return f"{self.service_name}_trends"
    
    def _get_from_cache(self, *args, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """キャッシュからデータを取得する（オプション）
        
        各マネージャーで必要に応じて実装
        デフォルトではNoneを返す（キャッシュを使用しない）
        """
        return None
    
    def _save_to_cache(self, data: List[Dict[str, Any]], *args, **kwargs) -> bool:
        """キャッシュにデータを保存する（オプション）
        
        各マネージャーで必要に応じて実装
        デフォルトではFalseを返す（キャッシュを保存しない）
        
        Returns:
            bool: 保存が成功した場合はTrue、失敗または未実装の場合はFalse
        """
        return False
    
    def _update_cache_status(self, cache_key: str, data_count: int, *args, **kwargs) -> bool:
        """cache_statusテーブルを更新する（オプション）
        
        各マネージャーで必要に応じて実装
        デフォルトではFalseを返す（更新しない）
        
        Args:
            cache_key: キャッシュキー
            data_count: データ件数
            *args, **kwargs: 追加パラメータ（countryなど）
        
        Returns:
            bool: 更新が成功した場合はTrue、失敗または未実装の場合はFalse
        """
        return False
    
    def _clear_cache(self, *args, **kwargs) -> bool:
        """キャッシュをクリアする（オプション）
        
        各マネージャーで必要に応じて実装
        デフォルトではFalseを返す（キャッシュをクリアしない）
        """
        return False
    
    def _apply_default_sorting(self, data: List[Dict[str, Any]], sort_key: Optional[str] = None, reverse: bool = True) -> List[Dict[str, Any]]:
        """デフォルトのソート処理
        
        Args:
            data: ソートするデータ
            sort_key: ソートキー（Noneの場合はrankでソート、文字列の場合はそのまま比較）
            reverse: 降順かどうか
        
        Returns:
            ソートされたデータ（rankも設定される）
        """
        if sort_key:
            # 数値キーのリスト（数値としてソートする必要があるキー）
            numeric_keys = ['stars', 'stars_count', 'forks', 'forks_count', 'average_user_rating', 
                          'user_rating_count', 'votes_count', 'reactions_count', 'sales_count', 
                          'review_count', 'price', 'change_percent', 'bookmark_count']
            
            # 数値キーの場合は数値として比較、それ以外は文字列として比較
            def get_sort_value(x):
                value = x.get(sort_key)
                # Noneの場合は、数値キーの場合は0、それ以外は空文字列として扱う
                if value is None:
                    return 0 if sort_key in numeric_keys else ''
                # 数値の場合は数値として返す
                if isinstance(value, (int, float)):
                    return value
                # 文字列の場合はそのまま返す
                return value
            
            data.sort(key=get_sort_value, reverse=reverse)
        else:
            # sort_keyがNoneの場合はrankでソート（既にrankが設定されている場合）
            data.sort(key=lambda x: x.get('rank', 0), reverse=reverse)
        
        # ランキングを設定
        for i, item in enumerate(data, 1):
            item['rank'] = i
        
        return data
    
    def get_trends(
        self,
        limit: int = 25,
        force_refresh: bool = False,
        auto_fetch_on_cache_miss: bool = True,  # キャッシュがない場合に自動的にAPIを呼び出すかどうか
        sort_key: Optional[str] = None,  # ソートキー（Noneの場合はrankでソート）
        sort_reverse: bool = True,  # 降順かどうか
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """トレンドデータを取得する（共通実装）
        
        Args:
            limit: 取得件数
            force_refresh: 強制更新フラグ
            auto_fetch_on_cache_miss: キャッシュがない場合に自動的にAPIを呼び出すかどうか
            sort_key: ソートキー（Noneの場合はrankでソート）
            sort_reverse: 降順かどうか
            *args, **kwargs: 各マネージャー固有のパラメータ（_fetch_trends、_get_from_cacheなどに渡される）
        
        Returns:
            Dict: {
                'success': bool,
                'data': List[Dict],
                'status': str ('cached' | 'api_fetched' | 'cache_not_found' | 'api_error'),
                'source': str,
                ... その他のメタデータ
            }
        """
        try:
            # force_refreshの場合はキャッシュをクリア
            if force_refresh:
                logger.info(f"🔄 {self.service_name}: force_refresh指定のためキャッシュをクリアします")
                self._clear_cache(*args, **kwargs)
            
            # キャッシュからデータを取得
            cached_data = None
            if not force_refresh:
                cached_data = self._get_from_cache(*args, **kwargs)
            
            # キャッシュデータがある場合はそれを返す
            if cached_data and len(cached_data) > 0:
                # デフォルトソートを適用
                cached_data = self._apply_default_sorting(cached_data, sort_key=sort_key, reverse=sort_reverse)
                logger.info(f"✅ {self.service_name}: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    'success': True,
                    'data': cached_data[:limit],
                    'status': 'cached',
                    'source': 'database_cache',
                    **kwargs  # その他のメタデータ（category, region, countryなど）を追加
                }
            
            # キャッシュがない場合の処理
            if not force_refresh and not auto_fetch_on_cache_miss:
                logger.warning(f"⚠️ {self.service_name}: キャッシュにデータがありませんが、auto_fetch_on_cache_miss=falseのため外部APIは呼び出しません")
                return {
                    'success': True,
                    'data': [],
                    'status': 'cache_not_found',
                    'source': 'database_cache',
                    **kwargs
                }
            
            # 外部APIからデータを取得
            logger.warning(f"⚠️ {self.service_name}: キャッシュデータが見つかりません。外部APIを呼び出します")
            api_result = self._fetch_trends(*args, limit=limit, **kwargs)
            
            if api_result and api_result.get('success') and api_result.get('data'):
                trends_data = api_result.get('data', [])
                
                # キャッシュに保存を試みる
                try:
                    save_success = self._save_to_cache(trends_data, *args, **kwargs)
                    if save_success:
                        logger.info(f"✅ {self.service_name}: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました")
                        
                        # cache_statusを更新（オプション）
                        try:
                            cache_key = self._get_cache_key(*args, **kwargs)
                            update_success = self._update_cache_status(cache_key, len(trends_data), *args, **kwargs)
                            if not update_success:
                                logger.debug(f"⚠️ {self.service_name}: cache_statusの更新をスキップしました（未実装または失敗）")
                        except Exception as e:
                            logger.warning(f"⚠️ {self.service_name}: cache_status更新中にエラーが発生しました: {e}")
                    else:
                        logger.warning(f"⚠️ {self.service_name}: データ取得成功しましたが、キャッシュ保存に失敗しました")
                except Exception as e:
                    logger.warning(f"⚠️ {self.service_name}: キャッシュ保存中にエラーが発生しました: {e}")
                
                # デフォルトソートを適用
                trends_data = self._apply_default_sorting(trends_data, sort_key=sort_key, reverse=sort_reverse)
                
                return {
                    'success': True,
                    'data': trends_data[:limit],
                    'status': 'api_fetched',
                    'source': api_result.get('source', 'external_api'),
                    **kwargs,
                    **{k: v for k, v in api_result.items() if k not in ['data', 'success', 'status', 'source']}
                }
            else:
                error_msg = api_result.get('error', 'Unknown error') if api_result else 'API call failed'
                logger.error(f"❌ {self.service_name}: 外部APIからデータを取得できませんでした: {error_msg}")
                return {
                    'success': False,
                    'data': [],
                    'status': 'api_error',
                    'error': error_msg,
                    **kwargs
                }
        
        except Exception as e:
            logger.error(f"❌ {self.service_name} トレンド取得エラー: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'{self.service_name}トレンドの取得に失敗しました: {str(e)}',
                'data': [],
                'status': 'error',
                **kwargs
            }
