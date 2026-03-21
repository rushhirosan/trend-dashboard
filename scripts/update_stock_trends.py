#!/usr/bin/env python3
"""
株価トレンドを手動で強制更新するスクリプト
JP（日本株）とUS（米国株）の両方のデータを更新します
"""
import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 環境変数を読み込み
load_dotenv()

from services.trends.stock_trends import StockTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)


def update_stock_trends():
    """株価トレンドを強制更新（JPとUSの両方）"""
    try:
        manager = StockTrendsManager()

        # JP（日本株）を更新
        logger.info("=" * 60)
        logger.info("🇯🇵 日本株の株価トレンドを強制更新中...")
        logger.info("=" * 60)
        result_jp = manager.get_trends(market="JP", limit=25, force_refresh=True)

        if result_jp.get("success"):
            data_count = len(result_jp.get("data", []))
            logger.info(f"✅ 日本株の更新完了: {data_count}件")
            logger.info(f"   ステータス: {result_jp.get('status')}")
            logger.info(f"   ソース: {result_jp.get('source')}")
        else:
            error = result_jp.get("error", "Unknown error")
            logger.error(f"❌ 日本株の更新失敗: {error}")

        print()

        # US（米国株）を更新
        logger.info("=" * 60)
        logger.info("🇺🇸 米国株の株価トレンドを強制更新中...")
        logger.info("=" * 60)
        result_us = manager.get_trends(market="US", limit=25, force_refresh=True)

        if result_us.get("success"):
            data_count = len(result_us.get("data", []))
            logger.info(f"✅ 米国株の更新完了: {data_count}件")
            logger.info(f"   ステータス: {result_us.get('status')}")
            logger.info(f"   ソース: {result_us.get('source')}")
        else:
            error = result_us.get("error", "Unknown error")
            logger.error(f"❌ 米国株の更新失敗: {error}")

        logger.info("=" * 60)
        logger.info("✅ 株価トレンドの強制更新が完了しました")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 株価トレンド更新エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    update_stock_trends()
