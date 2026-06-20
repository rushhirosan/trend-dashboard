#!/usr/bin/env python3
"""
定時スケジューラ用: JP または US のみ refresh_all_trends を実行する subprocess エントリ。

親 Gunicorn プロセスの RSS を抑え、フェーズごとに OS へメモリを返す。
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

from managers.trend_managers import refresh_all_trends
from utils.logger_config import get_logger

logger = get_logger(__name__)

RESULT_PREFIX = "REFRESH_RESULT_JSON:"


def _emit_result(result: dict) -> None:
    print(RESULT_PREFIX + json.dumps(result, ensure_ascii=False), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh trend caches for JP or US region")
    parser.add_argument("--region", choices=("jp", "us"), required=True)
    parser.add_argument("--max-concurrent", type=int, default=None)
    parser.add_argument("--batch-delay", type=float, default=None)
    args = parser.parse_args()

    os.environ.setdefault("ENABLE_SCHEDULER", "false")
    os.environ.setdefault("SKIP_STARTUP_EXECUTION", "true")

    try:
        from app import create_app
    except Exception as exc:
        logger.error("create_app import failed: %s", exc, exc_info=True)
        _emit_result({"success": False, "results": {}, "region": args.region, "error": str(exc)})
        return 1

    try:
        app, _scheduler = create_app()
    except Exception as exc:
        logger.error("create_app failed: %s", exc, exc_info=True)
        _emit_result({"success": False, "results": {}, "region": args.region, "error": str(exc)})
        return 1

    with app.app_context():
        managers = app.config.get("TREND_MANAGERS") or {}
        if not managers:
            _emit_result(
                {
                    "success": False,
                    "results": {},
                    "region": args.region,
                    "error": "managers_not_initialized",
                }
            )
            return 1
        try:
            result = refresh_all_trends(
                managers,
                force_refresh=True,
                max_concurrent=args.max_concurrent,
                batch_delay_seconds=args.batch_delay,
                region=args.region,
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

    _emit_result(result)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
