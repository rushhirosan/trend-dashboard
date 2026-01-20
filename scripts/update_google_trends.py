#!/usr/bin/env python3
"""
Googleトレンドを手動で更新するスクリプト
JPとUSの両方のデータを更新します
"""
import os
import sys
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 環境変数を読み込み
load_dotenv()

from services.trends.google_trends import GoogleTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

def update_google_trends():
    """Googleトレンドを更新（JPとUSの両方）"""
    try:
        manager = GoogleTrendsManager()
        
        # JPデータを更新
        logger.info("=" * 60)
        logger.info("🇯🇵 日本のGoogleトレンドを更新中...")
        logger.info("=" * 60)
        result_jp = manager.get_trends('JP', limit=25, force_refresh=True)
        
        if result_jp.get('success'):
            data_count = len(result_jp.get('data', []))
            logger.info(f"✅ 日本のGoogleトレンド更新完了: {data_count}件")
            logger.info(f"   ステータス: {result_jp.get('status')}")
            logger.info(f"   ソース: {result_jp.get('source')}")
            if 'refresh_date' in result_jp:
                logger.info(f"   データ日付: {result_jp.get('refresh_date')}")
        else:
            error = result_jp.get('error', 'Unknown error')
            logger.error(f"❌ 日本のGoogleトレンド更新失敗: {error}")
        
        print()  # 空行
        
        # レート制限を避けるため、リクエスト間に待機時間を追加
        import time
        logger.info("⏳ レート制限を避けるため、10秒待機します...")
        time.sleep(10)
        logger.info("✅ 待機完了")
        print()  # 空行
        
        # USデータを更新
        logger.info("=" * 60)
        logger.info("🇺🇸 USのGoogleトレンドを更新中...")
        logger.info("=" * 60)
        result_us = manager.get_trends('US', limit=25, force_refresh=True)
        
        if result_us.get('success'):
            data_count = len(result_us.get('data', []))
            logger.info(f"✅ USのGoogleトレンド更新完了: {data_count}件")
            logger.info(f"   ステータス: {result_us.get('status')}")
            logger.info(f"   ソース: {result_us.get('source')}")
            if 'refresh_date' in result_us:
                logger.info(f"   データ日付: {result_us.get('refresh_date')}")
        else:
            error = result_us.get('error', 'Unknown error')
            logger.error(f"❌ USのGoogleトレンド更新失敗: {error}")
        
        logger.info("=" * 60)
        logger.info("✅ Googleトレンドの更新処理が完了しました")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Googleトレンド更新エラー: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    update_google_trends()
