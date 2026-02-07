"""
トレンドマネージャーのベースクラス
共通の処理（rate_limiter初期化、キャッシュチェック、エラーハンドリング）を提供
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
import os
from database_config import TrendsCache
from utils.logger_config import get_logger
from utils.rate_limiter import get_rate_limiter
from utils.dummy_data_generator import generate_dummy_trends_data

logger = get_logger(__name__)

# AlertServiceを遅延インポート（オプション）
_alert_service = None

def _get_alert_service():
    """AlertServiceを取得（シングルトン）"""
    global _alert_service
    if _alert_service is None:
        try:
            from utils.alert_service import AlertService
            _alert_service = AlertService()
        except Exception as e:
            logger.debug(f"AlertService初期化エラー（アラート無効）: {e}")
            _alert_service = None
    return _alert_service


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

    def _is_dummy_mode(self) -> bool:
        """ダミーモードが有効かどうかをチェック

        環境変数 USE_DUMMY_DATA が true/1/yes のときに有効。
        """
        use_dummy = os.getenv("USE_DUMMY_DATA", "").strip().lower()
        return use_dummy in ("true", "1", "yes")

    def _generate_dummy_data(self, limit: int = 25, *args, **kwargs) -> List[Dict[str, Any]]:
        """ダミーデータを生成する（デフォルト実装）

        各マネージャーで必要に応じてオーバーライド可能。
        """
        return generate_dummy_trends_data(self.service_name, limit=limit, *args, **kwargs)

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

    def _format_source_data_for_alert(self, trends_data: List[Dict[str, Any]], error_exception: Optional[Exception] = None) -> Dict[str, str]:
        """エラーアラート用にソースデータをフォーマット

        Args:
            trends_data: 保存しようとしたデータ
            error_exception: 発生した例外（あれば）

        Returns:
            Dict: フォーマットされたデータ情報
        """
        info = {}

        # データの基本情報
        info["データ総件数"] = str(len(trends_data))

        # 最初の3件のサンプルデータ
        sample_count = min(3, len(trends_data))
        if sample_count > 0:
            samples = []
            for i, item in enumerate(trends_data[:sample_count]):
                # 各アイテムの主要フィールドを抽出（長すぎる場合は切り詰め）
                sample_item = {}
                for key, value in item.items():
                    if isinstance(value, str):
                        # 文字列は200文字に制限
                        sample_item[key] = value[:200] + "..." if len(value) > 200 else value
                    elif isinstance(value, (int, float, bool)) or value is None:
                        sample_item[key] = value
                    else:
                        sample_item[key] = str(value)[:200]
                samples.append(f"アイテム{i+1}: {sample_item}")

            info["サンプルデータ（最初の3件）"] = "\n".join(samples)

        # エラーに関連する可能性のあるデータを特定
        if error_exception:
            error_str = str(error_exception).lower()

            # StringDataRightTruncationエラーの場合、長いフィールドを特定
            if "stringdata" in error_str or "too long" in error_str or "truncation" in error_str:
                long_fields = []
                for i, item in enumerate(trends_data):
                    item_info = []
                    for key, value in item.items():
                        if isinstance(value, str) and len(value) > 255:
                            item_info.append(f"{key}: {len(value)}文字")
                    if item_info:
                        long_fields.append(f"アイテム{i+1} (rank={item.get('rank', 'N/A')}): {', '.join(item_info)}")

                if long_fields:
                    info["長いフィールド検出"] = "\n".join(long_fields[:5])  # 最初の5件まで

        # データの構造情報
        if trends_data:
            first_item = trends_data[0]
            info["データフィールド"] = ", ".join(list(first_item.keys())[:20])  # 最初の20フィールドまで

        return info

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
                          'review_count', 'price', 'change_percent', 'bookmark_count', 'score']

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
                'status': str ('cached' | 'api_fetched' | 'cache_not_found' | 'api_error' | 'dummy_cached' | 'dummy_generated'),
                'source': str,
                ... その他のメタデータ
            }
        """
        try:
            # --- ダミーモード（ローカル開発用） ---
            if self._is_dummy_mode():
                logger.info(f"🎭 {self.service_name}: ダミーモードが有効です。ダミーデータを処理します")

                # force_refresh の場合はキャッシュをクリア
                if force_refresh:
                    logger.info(f"🔄 {self.service_name}: (dummy) force_refresh指定のためキャッシュをクリアします")
                    self._clear_cache(*args, **kwargs)

                # まずキャッシュからダミーデータを取得
                cached_dummy_data: Optional[List[Dict[str, Any]]] = None
                if not force_refresh:
                    cached_dummy_data = self._get_from_cache(*args, **kwargs)

                if cached_dummy_data and len(cached_dummy_data) > 0:
                    cached_dummy_data = self._apply_default_sorting(
                        cached_dummy_data, sort_key=sort_key, reverse=sort_reverse
                    )
                    logger.info(f"✅ {self.service_name}: ダミーモード - キャッシュから{len(cached_dummy_data)}件のデータを取得しました")
                    return {
                        "success": True,
                        "data": cached_dummy_data[:limit],
                        "status": "dummy_cached",
                        "source": "dummy_database_cache",
                        **kwargs,
                    }

                # キャッシュがない場合はダミーデータを生成
                logger.info(f"⚠️ {self.service_name}: ダミーモードのキャッシュデータが見つかりません。新しくダミーデータを生成します")
                dummy_data = self._generate_dummy_data(limit=limit, *args, **kwargs)

                # キャッシュ保存はベストエフォート（失敗してもアラートは飛ばさない）
                try:
                    save_success = self._save_to_cache(dummy_data, *args, **kwargs)
                    if save_success:
                        logger.info(f"✅ {self.service_name}: ダミーデータ{len(dummy_data)}件を生成し、キャッシュに保存しました")
                        try:
                            cache_key = self._get_cache_key(*args, **kwargs)
                            self._update_cache_status(cache_key, len(dummy_data), *args, **kwargs)
                        except Exception as e:
                            logger.warning(f"⚠️ {self.service_name}: cache_status更新中にエラーが発生しました (ダミーモード): {e}")
                    else:
                        logger.warning(f"⚠️ {self.service_name}: ダミーデータ生成成功しましたが、キャッシュ保存に失敗しました")
                except Exception as e:
                    logger.warning(f"⚠️ {self.service_name}: ダミーデータキャッシュ保存中にエラーが発生しました: {e}", exc_info=True)

                dummy_data = self._apply_default_sorting(dummy_data, sort_key=sort_key, reverse=sort_reverse)
                return {
                    "success": True,
                    "data": dummy_data[:limit],
                    "status": "dummy_generated",
                    "source": "generated_dummy_data",
                    **kwargs,
                }

            # --- 通常モード（本番用） ---
            # force_refreshの場合はキャッシュをクリア
            if force_refresh:
                logger.info(f"🔄 {self.service_name}: force_refresh指定のためキャッシュをクリアします")
                self._clear_cache(*args, **kwargs)

            # キャッシュからデータを取得
            cached_data: Optional[List[Dict[str, Any]]] = None
            if not force_refresh:
                cached_data = self._get_from_cache(*args, **kwargs)

            # キャッシュデータがある場合はそれを返す
            if cached_data and len(cached_data) > 0:
                cached_data = self._apply_default_sorting(cached_data, sort_key=sort_key, reverse=sort_reverse)
                logger.info(f"✅ {self.service_name}: キャッシュから{len(cached_data)}件のデータを取得しました")
                return {
                    "success": True,
                    "data": cached_data[:limit],
                    "status": "cached",
                    "source": "database_cache",
                    **kwargs,  # その他のメタデータ（category, region, countryなど）を追加
                }

            # キャッシュがない場合の処理
            if not force_refresh and not auto_fetch_on_cache_miss:
                logger.warning(
                    f"⚠️ {self.service_name}: キャッシュにデータがありませんが、auto_fetch_on_cache_miss=falseのため外部APIは呼び出しません"
                )
                return {
                    "success": True,
                    "data": [],
                    "status": "cache_not_found",
                    "source": "database_cache",
                    **kwargs,
                }

            # 外部APIからデータを取得
            logger.warning(f"⚠️ {self.service_name}: キャッシュデータが見つかりません。外部APIを呼び出します")
            api_result = self._fetch_trends(*args, limit=limit, **kwargs)

            if api_result and api_result.get("success") and api_result.get("data"):
                trends_data = api_result.get("data", [])

                # キャッシュに保存を試みる
                cache_save_error: Optional[str] = None
                save_success = False
                error_exception: Optional[Exception] = None
                try:
                    save_success = self._save_to_cache(trends_data, *args, **kwargs)
                    if save_success:
                        logger.info(
                            f"✅ {self.service_name}: 外部APIから{len(trends_data)}件のデータを取得し、キャッシュに保存しました"
                        )

                        # cache_statusを更新（オプション）
                        try:
                            cache_key = self._get_cache_key(*args, **kwargs)
                            update_success = self._update_cache_status(cache_key, len(trends_data), *args, **kwargs)
                            if not update_success:
                                logger.debug(
                                    f"⚠️ {self.service_name}: cache_statusの更新をスキップしました（未実装または失敗）"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ {self.service_name}: cache_status更新中にエラーが発生しました: {e}")
                    else:
                        logger.warning(f"⚠️ {self.service_name}: データ取得成功しましたが、キャッシュ保存に失敗しました")
                        cache_save_error = "キャッシュ保存が失敗しました（_save_to_cacheがFalseを返しました）"
                except Exception as e:
                    error_msg = str(e)
                    error_exception = e
                    logger.warning(f"⚠️ {self.service_name}: キャッシュ保存中にエラーが発生しました: {e}", exc_info=True)
                    cache_save_error = f"キャッシュ保存中にエラーが発生しました: {error_msg}"

                # キャッシュ保存失敗時にDiscordにアラートを送信（エラー内容とソースデータを含める）
                if cache_save_error:
                    alert_service = _get_alert_service()
                    if alert_service:
                        try:
                            cache_key = self._get_cache_key(*args, **kwargs)

                            # ソースデータの詳細を準備（最初の3件のサンプルと、問題のあるデータの詳細）
                            source_data_info = self._format_source_data_for_alert(trends_data, error_exception)

                            # エラーの詳細情報を準備
                            error_details = {
                                "サービス名": self.service_name,
                                "キャッシュキー": cache_key,
                                "データ件数": str(len(trends_data)),
                                "エラーメッセージ": cache_save_error[:1000],  # 長すぎる場合は切り詰め
                            }

                            # エラーの種類とスタックトレース
                            if error_exception:
                                import traceback
                                error_details["エラータイプ"] = type(error_exception).__name__
                                tb_str = "".join(
                                    traceback.format_exception(
                                        type(error_exception), error_exception, error_exception.__traceback__
                                    )
                                )
                                error_details["スタックトレース"] = tb_str[:2000]  # 長すぎる場合は切り詰め

                            # ソースデータの情報を追加
                            error_details.update(source_data_info)

                            alert_service.send_alert(
                                "error",
                                f"キャッシュ保存エラー: {self.service_name}",
                                f"{self.service_name}のデータ取得は成功しましたが、キャッシュ保存に失敗しました。",
                                error_details,
                            )
                        except Exception as alert_error:
                            logger.warning(f"⚠️ Discordアラート送信エラー: {alert_error}")

                # デフォルトソートを適用
                trends_data = self._apply_default_sorting(trends_data, sort_key=sort_key, reverse=sort_reverse)

                return {
                    "success": True,
                    "data": trends_data[:limit],
                    "status": "api_fetched",
                    "source": api_result.get("source", "external_api"),
                    **kwargs,
                    **{k: v for k, v in api_result.items() if k not in ["data", "success", "status", "source"]},
                }
            else:
                error_msg = api_result.get("error", "Unknown error") if api_result else "API call failed"
                logger.error(f"❌ {self.service_name}: 外部APIからデータを取得できませんでした: {error_msg}")
                return {
                    "success": False,
                    "data": [],
                    "status": "api_error",
                    "error": error_msg,
                    **kwargs,
                }

        except Exception as e:
            logger.error(f"❌ {self.service_name} トレンド取得エラー: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"{self.service_name}トレンドの取得に失敗しました: {str(e)}",
                "data": [],
                "status": "error",
                **kwargs,
            }
