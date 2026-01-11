#!/usr/bin/env python3
"""
eBayトレンドデータを取得してキャッシュに保存するスクリプト
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from services.trends.ebay_trends import eBayTrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

def main():
    """eBayトレンドデータを取得してキャッシュに保存"""
    try:
        logger.info("🔄 eBayトレンドデータ取得開始")
        
        manager = eBayTrendsManager()
        
        # 認証情報の確認
        if not manager.client_id:
            logger.error("❌ EBAY_CLIENT_IDが設定されていません")
            sys.exit(1)
        
        if not manager.client_secret:
            logger.error("❌ EBAY_CLIENT_SECRETが設定されていません")
            sys.exit(1)
        
        logger.info(f"✅ 認証情報確認完了 (Client ID: {manager.client_id[:20]}...)")
        logger.info(f"   使用環境: {'サンドボックス' if manager.client_id.startswith('SBX-') else '本番'}")
        
        # データを取得（force_refresh=Trueでキャッシュを無視）
        result = manager.get_trends(limit=25, force_refresh=True)
        
        if result.get('success'):
            data = result.get('data', [])
            data_count = len(data)
            status = result.get('status', 'unknown')
            
            logger.info(f"✅ eBayトレンドデータ取得完了")
            logger.info(f"   ステータス: {status}")
            logger.info(f"   データ件数: {data_count}件")
            
            if data_count > 0:
                logger.info(f"   最初の商品: {data[0].get('title', 'N/A')[:50]}")
                logger.info(f"   価格: {data[0].get('currency', 'USD')} ${data[0].get('price', 'N/A')}")
            
            return 0
        else:
            error = result.get('error', 'Unknown error')
            status = result.get('status', 'unknown')
            logger.error(f"❌ eBayトレンドデータ取得失敗")
            logger.error(f"   ステータス: {status}")
            logger.error(f"   エラー: {error}")
            return 1
            
    except Exception as e:
        logger.error(f"❌ eBayトレンドデータ取得エラー: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
