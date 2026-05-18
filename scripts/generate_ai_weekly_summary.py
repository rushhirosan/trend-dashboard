#!/usr/bin/env python3
"""
直前に終了した ISO 週（月〜日）の日次サマリー Markdown を最大7件読み、
OpenAI Chat Completions で週次サマリー＋週のホットトピックを1ファイルに生成する。

入力は ``docs/summaries/daily/YYYY-MM-DD.md`` のみ（DB・公開トレンド API は使わない）。
日次の ``YYYY-MM-DD`` は **観測日（business_day）**（ファイル名 = トレンド対象の暦日。
翌朝 06:50 JST 前後に生成されても、日曜分は ``…/2026-05-18.md`` のように日曜の日付）。
週次は対象週の月曜〜日曜について ``{mon}..{sun}.md`` を順に探す。詳細は
``docs/summaries/weekly/README.md``。

  export OPENAI_API_KEY=sk-...
  python scripts/generate_ai_weekly_summary.py --dry-run
  python scripts/generate_ai_weekly_summary.py --write --force

既定の対象週: JST の直前に終了した ISO 週（= 今週月曜の7日前が週の月曜）。
``--weekly-for-date YYYY-MM-DD`` で、その日を含む ISO 週を指定可。

  python scripts/generate_ai_weekly_summary.py --weekly-for-date 2026-05-14 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

JST = ZoneInfo("Asia/Tokyo")
REPO_ROOT = Path(__file__).resolve().parents[1]
DAILY_DIR = REPO_ROOT / "docs" / "summaries" / "daily"
WEEKLY_DIR = REPO_ROOT / "docs" / "summaries" / "weekly"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_USER_CHARS = 100_000


def iso_week_stem(d: date) -> str:
    iso_y, iso_w, _ = d.isocalendar()
    return f"{iso_y}-W{iso_w:02d}"


def week_range_mon_sun(any_day_in_week: date) -> Tuple[date, date]:
    mon = any_day_in_week - timedelta(days=any_day_in_week.isoweekday() - 1)
    sun = mon + timedelta(days=6)
    return mon, sun


def week_dates(mon: date) -> List[date]:
    return [mon + timedelta(days=i) for i in range(7)]


def default_week_mon_jst(now: Optional[datetime] = None) -> date:
    """直前に終了した ISO 週の月曜（JST カレンダー）。"""
    if now is None:
        now = datetime.now(JST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)
    today = now.date()
    this_mon = today - timedelta(days=today.isoweekday() - 1)
    return this_mon - timedelta(days=7)


def split_front_matter(raw: str) -> Tuple[str, str]:
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def load_daily_markdown(daily_path: Path) -> Optional[str]:
    if not daily_path.is_file():
        return None
    raw = daily_path.read_text(encoding="utf-8")
    _, body = split_front_matter(raw)
    return body.strip() or None


def build_rollups(
    mon: date, sun: date, daily_dir: Path
) -> Tuple[str, Dict[str, Any]]:
    """LLM 用テキストとメタ（欠損日など）。各 ``d`` は business_day（観測日）のファイル名。"""
    meta: Dict[str, Any] = {
        "week_mon": mon.isoformat(),
        "week_sun": sun.isoformat(),
        "iso_week": iso_week_stem(mon),
        "daily_files": [],
        "missing_dates": [],
    }
    chunks: List[str] = []
    for d in week_dates(mon):
        rel = f"docs/summaries/daily/{d.isoformat()}.md"
        p = daily_dir / f"{d.isoformat()}.md"
        body = load_daily_markdown(p)
        entry = {"date": d.isoformat(), "path": rel, "found": body is not None}
        meta["daily_files"].append(entry)
        if body is None:
            meta["missing_dates"].append(d.isoformat())
            chunks.append(f"## 日次サマリー — {d.isoformat()}（JST）\n\n（ファイルなし: {rel}）\n")
        else:
            chunks.append(f"## 日次サマリー — {d.isoformat()}（JST）\n\n{body}\n")

    text = "\n".join(chunks).strip()
    if len(text) > MAX_USER_CHARS:
        text = text[:MAX_USER_CHARS] + "\n…(truncated)"
        meta["truncated"] = True
    else:
        meta["truncated"] = False
    return text, meta


def call_openai(
    system: str,
    user: str,
    api_key: str,
    model: str,
    timeout: int = 180,
) -> str:
    r = requests.post(
        OPENAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.35,
            "max_tokens": 8192,
        },
        timeout=timeout,
    )
    if not r.ok:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:2000]}")
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenAI response missing choices: {str(data)[:2000]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not content or not isinstance(content, str):
        raise RuntimeError("OpenAI response missing message.content")
    return content.strip()


def strip_wrapping_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def merge_front_matter(
    iso_week: str,
    mon: date,
    sun: date,
    model: str,
    inner_markdown: str,
    daily_meta: Dict[str, Any],
) -> str:
    gen_at = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    range_s = f"{mon.isoformat()} 〜 {sun.isoformat()}"
    n_found = sum(1 for x in daily_meta.get("daily_files", []) if x.get("found"))
    fm = f"""---
status: draft
iso_week: "{iso_week}"
week_range_jst: "{range_s}"
reviewer: ""
reviewed_at: ""
generator: openai
model: "{model}"
daily_files_found: {n_found}
daily_files_expected: 7
missing_daily_dates: {json.dumps(daily_meta.get("missing_dates") or [], ensure_ascii=False)}
generated_at: "{gen_at}"
---

"""
    body = strip_wrapping_fences(inner_markdown)
    return fm + body


SYSTEM_PROMPT = """あなたはトレンドダッシュボードの編集者だ。入力は、ある1週間（ISO 週・月曜始まり）
の各日について、すでにリポジトリに存在する「日次サマリー」Markdown の本文だけである。
各日の見出し日付（YYYY-MM-DD）は **その日のトレンド観測日（business_day）** であり、
ファイルが週のあとに生成されたこととは無関係に扱う。
新たに Web やトレンド API を参照したり、スナップショットを読んだりしない。

次を厳守すること:
- 出力は日本語の Markdown のみ（YAML フロントマターは書かない。先頭から # 見出しでよい）。
- 次の2パートを、この順で、かつ中間に区切り線 `---` を1行だけ挟むこと:
  1) 週次サマリー: テンプレに相当する見出し構造:
     - `# 週次サマリー — ISO_WEEK（対象週 JST WEEK_MON〜WEEK_SUN）`（ISO_WEEK / WEEK_MON / WEEK_SUN はユーザメッセージ先頭の JSON にある文字列をそのまま使う）
     - `- **対象週**:` と `- **生成・送信完了**:` の2行（生成時刻は「自動生成（時刻未入力）」でよい）
     - `## 今週の流れ（短文）`
     - `## 来週に残る論点（2〜4）`
     - `## ソース一覧（週を通じた根拠リンク）`（日次に出ていたリンクのみ。新しい URL を捏造しない）
  2) 週のホットトピック:
     - `# 週のホットトピック — ISO_WEEK（同上の週）`
     - 短い選定基準の箇条書き
     - `## 1.` … `## 2.` … のように番号見出しで 3〜7 件（日次で繰り返し出た論点を優先）
- 「今週の流れ」は日次の繰り返しにせず、週としての要約にする。
- 日次ファイルが欠けている日がある場合は、`## データ前提` を週次パートの末尾（ソース一覧の前でも可）に短く置き、欠損日を列挙する。
- 憶測・未確認の断定は避け、「日次サマリー上は…」と書く。"""


def run_generate(
    week_mon: date,
    api_key: str,
    model: str,
    daily_dir: Path,
) -> Tuple[str, Dict[str, Any]]:
    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)
    roll, meta = build_rollups(week_mon, week_sun, daily_dir)
    meta["iso_week"] = stem

    n_found = sum(1 for x in meta.get("daily_files", []) if x.get("found"))
    if n_found == 0:
        meta["error"] = "no_daily_files"
        return "", meta

    header = json.dumps(
        {
            "iso_week": stem,
            "week_mon_jst": week_mon.isoformat(),
            "week_sun_jst": week_sun.isoformat(),
            "daily_file_dates_are_business_days": True,
            "missing_daily_dates": meta.get("missing_dates", []),
        },
        ensure_ascii=False,
    )
    user = f"{header}\n\n--- 以下、日次サマリー本文（7日分。欠損は見出しに注記あり） ---\n\n{roll}"
    inner = call_openai(SYSTEM_PROMPT, user, api_key, model)
    meta["model"] = model
    full = merge_front_matter(stem, week_mon, week_sun, model, inner, meta)
    return full, meta


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(
        description="Generate weekly AI summary from docs/summaries/daily/*.md"
    )
    p.add_argument(
        "--weekly-for-date",
        metavar="YYYY-MM-DD",
        help="Summarize the ISO week containing this date (default: last completed week, JST)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Without API key: print input manifest + rollups excerpt. With key: print markdown",
    )
    p.add_argument("--write", action="store_true", help="Write docs/summaries/weekly/{ISO}.md")
    p.add_argument("--force", action="store_true", help="Overwrite existing file")
    p.add_argument(
        "--daily-dir",
        type=Path,
        default=None,
        help="Override daily summaries directory (default: repo docs/summaries/daily)",
    )
    args = p.parse_args()

    if args.weekly_for_date:
        anchor = date.fromisoformat(args.weekly_for_date)
        week_mon, _ = week_range_mon_sun(anchor)
    else:
        week_mon = default_week_mon_jst()

    week_sun = week_mon + timedelta(days=6)
    stem = iso_week_stem(week_mon)
    daily_dir = args.daily_dir if args.daily_dir is not None else DAILY_DIR

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_SUMMARY_MODEL") or "gpt-4o-mini").strip()

    roll, meta = build_rollups(week_mon, week_sun, daily_dir)

    if args.dry_run and not api_key:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        print("\n--- rollups preview (first 4000 chars) ---\n", file=sys.stderr)
        print(roll[:4000], file=sys.stderr)
        if len(roll) > 4000:
            print("\n…", file=sys.stderr)
        print(
            "\n(set OPENAI_API_KEY to generate weekly markdown)",
            file=sys.stderr,
        )
        return 0

    if not api_key:
        print(
            "❌ OPENAI_API_KEY が未設定です（--dry-run のみ、キーなしではマニフェストを出せます）",
            file=sys.stderr,
        )
        return 1

    text, meta = run_generate(week_mon, api_key, model, daily_dir)
    if meta.get("error") == "no_daily_files":
        print(
            f"❌ {week_mon.isoformat()}〜{week_sun.isoformat()} の週で、"
            f"docs/summaries/daily/*.md が1件も見つかりません。",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(text)
        return 0

    if not args.write:
        print(text)
        return 0

    out = WEEKLY_DIR / f"{stem}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        print(f"skip (exists): {out.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 0

    out.write_text(text, encoding="utf-8")
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
