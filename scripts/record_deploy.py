#!/usr/bin/env python3
"""
デプロイ時刻を DB に記録する。Fly.io の release_command から呼ぶ。
起動時補完は「直近デプロイならスキップ」するため、この記録でデプロイとクラッシュを区別する。
"""
import os
import sys

# プロジェクトルートを path に追加
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
os.chdir(_root)

from dotenv import load_dotenv
load_dotenv()

from database_config import TrendsCache

def main():
    cache = TrendsCache()
    if not cache.pool:
        cache.connect()
    if not cache.pool:
        print("⚠️ データベース接続に失敗しました。deploy_marker は更新されません。", file=sys.stderr)
        sys.exit(1)
    if hasattr(cache, "ensure_scheduler_lock_ready"):
        cache.ensure_scheduler_lock_ready()
    ok = cache.record_deploy_timestamp()
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
