#!/usr/bin/env python3
"""
楽天トレンドを手動で更新するスクリプト
本番キャッシュを force_refresh で更新します（スケジューラと同じ「全ジャンル」）
"""
import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 環境変数を読み込み
load_dotenv()

from services.trends.rakuten_trends import RakutenTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)


def update_rakuten_trends():
    """楽天トレンドを更新（全ジャンル・スケジューラと同じ条件）"""
    try:
        manager = RakutenTrendsManager()

        logger.info("=" * 60)
        logger.info("🛒 楽天トレンドを更新中（全ジャンルランキング）...")
        logger.info("=" * 60)

        # genre_id なし = 'all' 扱い。楽天APIには genreId を送らず全ジャンルランキングを取得
        result = manager.get_trends(genre_id=None, limit=25, force_refresh=True)

        if result.get("success"):
            data_count = len(result.get("data", []))
            logger.info(f"✅ 楽天トレンド更新完了: {data_count}件")
            logger.info(f"   ステータス: {result.get('status')}")
            logger.info(f"   ソース: {result.get('source')}")
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"❌ 楽天トレンド更新失敗: {error}")
            sys.exit(1)

        logger.info("=" * 60)
        logger.info("✅ 楽天トレンドの手動更新が完了しました")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 楽天トレンド更新エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    update_rakuten_trends()
