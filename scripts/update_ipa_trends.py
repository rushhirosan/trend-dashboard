#!/usr/bin/env python3
"""
IPA注意喚起のキャッシュを更新するスクリプト
"""

import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trends.ipa_trends import IPATrendsManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

def main():
    """IPA注意喚起のキャッシュを更新"""
    try:
        logger.info("🔄 IPA注意喚起のキャッシュ更新を開始...")
        
        # IPA Trends Managerを初期化
        manager = IPATrendsManager()
        
        # force_refresh=Trueでキャッシュを更新
        result = manager.get_trends(limit=25, force_refresh=True)
        
        if result.get('success'):
            data_count = len(result.get('data', []))
            status = result.get('status', 'unknown')
            logger.info(f"✅ IPA注意喚起のキャッシュ更新完了: {data_count}件 ({status})")
            return 0
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"❌ IPA注意喚起のキャッシュ更新失敗: {error}")
            return 1
            
    except Exception as e:
        logger.error(f"❌ IPA注意喚起のキャッシュ更新エラー: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
