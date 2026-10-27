#!/usr/bin/env python3
"""画像の無い日次ブリーフにサムネを付ける。

同じ話題が続いている日は、直前の画像をコピーする。話題が変わった日は
OPENAI_API_KEY があれば 256px のフラットな絵を作る。鍵が無い、または
生成に失敗した日は画像なしのままにする。

使い方:
  python scripts/attach_daily_thumbs.py
  python scripts/attach_daily_thumbs.py --date 2026-10-26 --region jp
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.summary.daily_thumbs import attach_missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="", help="この観測日だけ処理する（YYYY-MM-DD）")
    parser.add_argument("--region", choices=("jp", "us", "both"), default="both")
    args = parser.parse_args()
    regions = ("jp", "us") if args.region == "both" else (args.region,)
    return attach_missing(only_date=args.date.strip(), regions=regions)


if __name__ == "__main__":
    sys.exit(main())
