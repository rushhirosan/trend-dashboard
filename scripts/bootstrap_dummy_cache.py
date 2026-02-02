#!/usr/bin/env python3
"""
ダミーデータを全カテゴリにキャッシュするスクリプト
ローカル開発環境でUI/UXの確認用に使用

使用方法:
    python scripts/bootstrap_dummy_cache.py

このスクリプトを実行すると:
1. 全カテゴリのマネージャーに対してダミーモードで25件ずつダミーデータを生成
2. 生成したダミーデータをデータベースキャッシュに保存
3. 以降、通常モードでアプリを起動してもキャッシュからダミーデータが表示される
"""

import os
import sys
import inspect
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# このスクリプト実行中だけダミーモードをONにする
os.environ["USE_DUMMY_DATA"] = "true"

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# インポートエラーをキャッチ
try:
    from app import create_app
    from managers.trend_managers import initialize_managers
    from utils.logger_config import get_logger
except ImportError as e:
    print("=" * 60)
    print("❌ インポートエラーが発生しました")
    print("=" * 60)
    print(f"エラー: {e}")
    print("")
    print("💡 解決方法:")
    print("   依存関係がインストールされていないようです。")
    print("   以下のコマンドで依存関係をインストールしてください:")
    print("")
    print("   pip install -r requirements.txt")
    print("")
    print("   インストール後、再度スクリプトを実行してください:")
    print("   python scripts/bootstrap_dummy_cache.py")
    print("=" * 60)
    sys.exit(1)

logger = get_logger(__name__)


def get_valid_kwargs_for_manager(manager, default_kwargs):
    """
    マネージャーのget_trendsメソッドのシグネチャを確認し、
    有効な引数だけを返す
    
    Args:
        manager: トレンドマネージャーインスタンス
        default_kwargs: デフォルトの引数辞書
    
    Returns:
        dict: 有効な引数のみを含む辞書
    """
    try:
        # get_trendsメソッドのシグネチャを取得
        sig = inspect.signature(manager.get_trends)
        
        # 有効な引数だけをフィルタリング
        valid_kwargs = {}
        for key, value in default_kwargs.items():
            if key in sig.parameters:
                valid_kwargs[key] = value
        
        return valid_kwargs
    except Exception as e:
        # エラーが発生した場合は、デフォルトの引数を使う
        logger.debug(f"シグネチャ取得エラー ({manager.service_name}): {e}")
        return default_kwargs


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("🎭 ダミーデータキャッシュ生成スクリプト開始")
    logger.info("=" * 60)
    
    try:
        # Flaskアプリとスケジューラーを初期化（スケジューラーは使用しない）
        app, scheduler = create_app()
        
        # 全カテゴリのマネージャーを初期化
        logger.info("📦 全カテゴリのマネージャーを初期化中...")
        managers = initialize_managers()
        
        if not managers:
            logger.error("❌ マネージャーの初期化に失敗しました")
            sys.exit(1)
        
        logger.info(f"✅ {len(managers)}個のマネージャーを初期化しました")
        logger.info("")
        
        # Flaskアプリコンテキスト内で実行
        with app.app_context():
            success_count = 0
            fail_count = 0
            
            logger.info("🔄 各カテゴリにダミーデータを生成中（limit=25）...")
            logger.info("")
            
            for key, manager in managers.items():
                try:
                    # stock は JP/US 両方にダミーを投入する
                    if key == "stock":
                        stock_ok = 0
                        for mkt in ("JP", "US"):
                            logger.info(f"📝 [{key}] ダミーデータ生成中 (market={mkt})...")
                            result = manager.get_trends(market=mkt, limit=25, force_refresh=True)
                            if result.get("success") and result.get("data"):
                                data_count = len(result.get("data", []))
                                logger.info(f"  ✅ [{key}] market={mkt} 完了: {data_count}件生成")
                                stock_ok += 1
                            else:
                                logger.warning(f"  ⚠️ [{key}] market={mkt} 失敗: {result.get('error', 'Unknown error')}")
                        if stock_ok == 2:
                            success_count += 1
                        else:
                            fail_count += 1
                        continue
                    
                    # movie, book は country=JP を明示（日本版で表示するため）
                    if key in ("movie", "book"):
                        extra_kwargs = {"country": "JP"}
                    else:
                        extra_kwargs = {}
                    
                    logger.info(f"📝 [{key}] ダミーデータ生成中...")
                    
                    # デフォルトの引数を準備（movie/bookはcountry=JPを追加）
                    default_kwargs = {
                        "limit": 25,
                        "force_refresh": True,
                        "auto_fetch_on_cache_miss": True,
                        **extra_kwargs,
                    }
                    
                    # マネージャーのシグネチャに合わせて有効な引数だけを取得
                    valid_kwargs = get_valid_kwargs_for_manager(manager, default_kwargs)
                    
                    # ダミーモードで get_trends を呼び出す
                    result = manager.get_trends(**valid_kwargs)
                    
                    if result.get("success") and result.get("data"):
                        data_count = len(result.get("data", []))
                        status = result.get("status", "unknown")
                        logger.info(
                            f"  ✅ [{key}] 完了: {data_count}件生成 "
                            f"(status={status})"
                        )
                        success_count += 1
                    else:
                        error_msg = result.get("error", "Unknown error")
                        logger.warning(
                            f"  ⚠️ [{key}] 失敗: {error_msg}"
                        )
                        fail_count += 1
                        
                except Exception as e:
                    logger.error(
                        f"  ❌ [{key}] エラー: {type(e).__name__}: {e}",
                        exc_info=True
                    )
                    fail_count += 1
            
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"✅ ダミーデータキャッシュ生成完了")
            logger.info(f"   成功: {success_count}個")
            logger.info(f"   失敗: {fail_count}個")
            logger.info("=" * 60)
            logger.info("")
            logger.info("💡 次のステップ:")
            logger.info("   ローカルでアプリを起動する際は .env に USE_DUMMY_DATA=true を設定してください。")
            logger.info("   すべてのソース（株価含む）がダミーのみ使用・保存され、実データは取得しません。")
            logger.info("")
            
    except Exception as e:
        logger.error(f"❌ スクリプト実行エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
