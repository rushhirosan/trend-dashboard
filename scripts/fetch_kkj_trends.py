#!/usr/bin/env python3
"""
官公需（Public Sector Signals）データを取得してキャッシュに保存するスクリプト。
キーワード別件数（直近30日）・県別Top5・キーワード別月次件数を取得。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from services.trends.kkj_trends import KKJTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)


def main():
    """官公需データを取得してキャッシュに保存"""
    try:
        logger.info("🔄 官公需データ取得開始")
        manager = KKJTrendsManager()
        result = manager.get_public_sector_signals(force_refresh=True, cache_only=False)

        if not result.get("success"):
            logger.error("❌ 官公需データ取得失敗: %s", result.get("error", "Unknown"))
            return 1

        data = result.get("data") or {}
        status = result.get("status", "unknown")
        logger.info("✅ 官公需データ取得完了 (status: %s)", status)

        signals = data.get("signals") or []
        for s in signals:
            logger.info("   キーワード別件数: %s = %s件", s.get("label"), s.get("count"))

        rankings = data.get("prefecture_rankings") or {}
        for key, label in [("ai", "AI"), ("dx", "DX"), ("cyber", "サイバー")]:
            top5 = rankings.get(key) or []
            names = [r.get("name") for r in top5[:5]]
            logger.info("   県別 %s Top5: %s", label, names if names else "—")

        monthly = data.get("signals_monthly") or {}
        if monthly.get("ai"):
            recent = monthly["ai"][:3]
            logger.info("   月次（AI・直近3ヶ月）: %s", [(m.get("period"), m.get("value")) for m in recent])

        return 0
    except Exception as e:
        logger.error("❌ 官公需データ取得エラー: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
