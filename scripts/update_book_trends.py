#!/usr/bin/env python3
"""
本トレンドを手動で更新するスクリプト
全カテゴリを force_refresh でAPIから取得しキャッシュを更新します。
日本: 総合・文芸・ビジネス・人文・社会・実用・IT
US: All, Fiction, Business, Biography & History, Science & Tech
"""
import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 環境変数を読み込み
load_dotenv()

from services.trends.book_trends import BookTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

# 日本: 5択カテゴリ
JP_CATEGORIES = ('all', 'fiction', 'business', 'humanities', 'practical')
# US: 5択カテゴリ
US_CATEGORIES = ('all', 'fiction', 'business', 'biography', 'science')


def update_book_trends():
    """本トレンドを全カテゴリ更新"""
    try:
        book_manager = BookTrendsManager()

        logger.info("=" * 60)
        logger.info("📚 本トレンドを更新中（全カテゴリ）...")
        logger.info("=" * 60)

        success_count = 0
        for country, categories in [('JP', JP_CATEGORIES), ('US', US_CATEGORIES)]:
            for cat in categories:
                result = book_manager.get_trends(
                    country=country,
                    limit=25,
                    force_refresh=True,
                    category=cat
                )
                if result.get('success'):
                    data_count = len(result.get('data', []))
                    logger.info(f"  ✅ {country} {cat}: {data_count}件")
                    success_count += 1
                else:
                    logger.warning(f"  ⚠️ {country} {cat}: {result.get('error', 'Unknown error')}")

        logger.info("=" * 60)
        logger.info(f"✅ 本トレンドの手動更新が完了しました ({success_count}/{len(JP_CATEGORIES) + len(US_CATEGORIES)} カテゴリ)")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ 本トレンド更新エラー: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    update_book_trends()
