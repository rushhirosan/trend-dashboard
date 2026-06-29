#!/usr/bin/env python3
"""
定時スケジューラ用: JP または US のみ refresh_all_trends を実行する subprocess エントリ。

親 Gunicorn プロセスの RSS を抑え、フェーズごとに OS へメモリを返す。
当該 chunk で必要なマネージャーのみ初期化（create_app 全量ロードはしない）。
結果は stdout 末尾行 `REFRESH_RESULT_JSON:{...}` で返す。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv()

from managers.trend_managers import compact_refresh_result, managers_for_refresh, refresh_all_trends
from utils.logger_config import get_logger

logger = get_logger(__name__)

RESULT_PREFIX = "REFRESH_RESULT_JSON:"


def _emit_result(result: dict) -> None:
    line = RESULT_PREFIX + json.dumps(result, ensure_ascii=False)
    print(line, flush=True)
    result_file = os.environ.get("REFRESH_RESULT_FILE")
    if not result_file:
        return
    try:
        with open(result_file, "w", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        logger.warning("⚠️ REFRESH_RESULT_FILE 書き込み失敗 %s: %s", result_file, exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh trend caches for JP or US region")
    parser.add_argument("--region", choices=("jp", "us"), required=True)
    parser.add_argument("--max-concurrent", type=int, default=None)
    parser.add_argument("--batch-delay", type=float, default=None)
    parser.add_argument("--jp-chunk", type=int, default=None, help="JP 分割番号 (1始まり)")
    parser.add_argument("--jp-chunks", type=int, default=None, help="JP 分割数")
    args = parser.parse_args()

    if args.region != "jp" and (args.jp_chunk is not None or args.jp_chunks is not None):
        _emit_result(
            {
                "success": False,
                "results": {},
                "region": args.region,
                "error": "jp_chunk_args_require_region_jp",
            }
        )
        return 1

    os.environ.setdefault("ENABLE_SCHEDULER", "false")
    os.environ.setdefault("SKIP_STARTUP_EXECUTION", "true")

    try:
        managers = managers_for_refresh(
            args.region,
            jp_chunk=args.jp_chunk,
            jp_chunks=args.jp_chunks,
        )
    except Exception as exc:
        logger.error("managers_for_refresh failed: %s", exc, exc_info=True)
        _emit_result({"success": False, "results": {}, "region": args.region, "error": str(exc)})
        return 1

    if not managers:
        _emit_result(
            {
                "success": True,
                "results": {},
                "region": args.region,
                "message": "no_tasks_for_chunk",
            }
        )
        return 0

    try:
        result = refresh_all_trends(
            managers,
            force_refresh=True,
            max_concurrent=args.max_concurrent,
            batch_delay_seconds=args.batch_delay,
            region=args.region,
            jp_chunk=args.jp_chunk,
            jp_chunks=args.jp_chunks,
        )
    except Exception as exc:
        logger.error("refresh_all_trends failed: %s", exc, exc_info=True)
        _emit_result(
            {
                "success": False,
                "results": {},
                "region": args.region,
                "error": str(exc),
            }
        )
        return 1

    _emit_result(compact_refresh_result(result))
    # 個別ソース失敗でも subprocess は正常終了（残り JP chunk / US を継続する）
    return 0


if __name__ == "__main__":
    sys.exit(main())
