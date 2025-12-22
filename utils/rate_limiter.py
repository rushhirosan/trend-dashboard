"""
統一的なレート制限ユーティリティ
各トレンドマネージャーで使用する共通のレート制限機能を提供
"""

import time
from collections import deque
from typing import Optional
from utils.logger_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """レート制限を管理するクラス"""
    
    def __init__(self, max_requests: int, window_seconds: int, name: str = "API"):
        """
        レート制限を初期化
        
        Args:
            max_requests: 時間窓内の最大リクエスト数
            window_seconds: 時間窓（秒）
            name: API名（ログ用）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self.requests = deque()  # リクエスト時刻のキュー
        
        logger.debug(f"RateLimiter初期化: {name} - {max_requests}リクエスト/{window_seconds}秒")
    
    def wait_if_needed(self) -> None:
        """
        レート制限をチェックし、必要に応じて待機
        
        このメソッドは、リクエストを送信する前に呼び出す必要があります。
        レート制限に達している場合は、自動的に待機します。
        """
        now = time.time()
        
        # 時間窓外の古いリクエストを削除
        while self.requests and now - self.requests[0] > self.window_seconds:
            self.requests.popleft()
        
        # レート制限に達している場合は待機
        if len(self.requests) >= self.max_requests:
            oldest_request = self.requests[0]
            sleep_time = self.window_seconds - (now - oldest_request) + 1  # 1秒のバッファ
            
            if sleep_time > 0:
                logger.info(f"⏳ {self.name} レート制限: {sleep_time:.1f}秒待機します（{len(self.requests)}/{self.max_requests}リクエスト）")
                time.sleep(sleep_time)
                
                # 待機後に再度古いリクエストを削除
                now = time.time()
                while self.requests and now - self.requests[0] > self.window_seconds:
                    self.requests.popleft()
        
        # 現在のリクエストを記録
        self.requests.append(time.time())
    
    def can_make_request(self) -> bool:
        """
        現在リクエストを送信できるかどうかをチェック（待機しない）
        
        Returns:
            bool: リクエスト可能な場合True
        """
        now = time.time()
        
        # 時間窓外の古いリクエストを削除
        while self.requests and now - self.requests[0] > self.window_seconds:
            self.requests.popleft()
        
        return len(self.requests) < self.max_requests
    
    def get_remaining_requests(self) -> int:
        """
        残りのリクエスト数を取得
        
        Returns:
            int: 残りのリクエスト数
        """
        now = time.time()
        
        # 時間窓外の古いリクエストを削除
        while self.requests and now - self.requests[0] > self.window_seconds:
            self.requests.popleft()
        
        return max(0, self.max_requests - len(self.requests))
    
    def reset(self) -> None:
        """レート制限の履歴をリセット"""
        self.requests.clear()
        logger.debug(f"{self.name} レート制限をリセットしました")


# 各APIのデフォルトレート制限設定
# 実際のAPI仕様に基づいて設定（保守的な値）
API_RATE_LIMITS = {
    'youtube': {'max_requests': 100, 'window_seconds': 100},  # 100リクエスト/100秒（保守的）
    'spotify': {'max_requests': 10, 'window_seconds': 1},    # 10リクエスト/秒
    'worldnews': {'max_requests': 10, 'window_seconds': 60}, # 10リクエスト/分（保守的）
    'podcast': {'max_requests': 10, 'window_seconds': 60},   # 10リクエスト/分（保守的）
    'rakuten': {'max_requests': 10, 'window_seconds': 1},   # 10リクエスト/秒（保守的）
    'twitch': {'max_requests': 800, 'window_seconds': 60},   # 800リクエスト/分
    'google': {'max_requests': 10, 'window_seconds': 60},    # 10リクエスト/分（保守的）
    'stock': {'max_requests': 20, 'window_seconds': 60},     # 20リクエスト/分（yfinance）
    'crypto': {'max_requests': 10, 'window_seconds': 60},    # 10リクエスト/分（CoinGecko）
    'news': {'max_requests': 10, 'window_seconds': 60},      # 10リクエスト/分（News API）
    'nhk': {'max_requests': 10, 'window_seconds': 60},       # 10リクエスト/分（保守的）
    'hatena': {'max_requests': 10, 'window_seconds': 60},    # 10リクエスト/分（保守的）
    'hackernews': {'max_requests': 10, 'window_seconds': 60}, # 10リクエスト/分（保守的）
    'cnn': {'max_requests': 10, 'window_seconds': 60},       # 10リクエスト/分（News API）
}


def get_rate_limiter(api_name: str, max_requests: Optional[int] = None, window_seconds: Optional[int] = None) -> RateLimiter:
    """
    指定されたAPI用のレート制限オブジェクトを取得
    
    Args:
        api_name: API名（'youtube', 'spotify'など）
        max_requests: カスタム最大リクエスト数（指定しない場合はデフォルト値を使用）
        window_seconds: カスタム時間窓（指定しない場合はデフォルト値を使用）
    
    Returns:
        RateLimiter: レート制限オブジェクト
    """
    api_name_lower = api_name.lower()
    
    if max_requests is None or window_seconds is None:
        # デフォルト設定を使用
        if api_name_lower in API_RATE_LIMITS:
            config = API_RATE_LIMITS[api_name_lower]
            max_requests = max_requests or config['max_requests']
            window_seconds = window_seconds or config['window_seconds']
        else:
            # デフォルト値（保守的）
            max_requests = max_requests or 10
            window_seconds = window_seconds or 60
            logger.warning(f"⚠️ {api_name}のレート制限設定が見つかりません。デフォルト値を使用します（{max_requests}リクエスト/{window_seconds}秒）")
    
    return RateLimiter(max_requests, window_seconds, name=api_name.upper())
