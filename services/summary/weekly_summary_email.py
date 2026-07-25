"""週次サマリーのメール本文（HTML / テキスト）。画像・添付なし。

実装は summary_markdown_email に集約。ここは互換 API を維持する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from services.summary.summary_markdown_email import (
    markdown_to_email_html,
    markdown_to_email_text,
    strip_front_matter,
    strip_legacy_charts,
)

# 旧テスト・呼び出し向けエイリアス
strip_legacy_weekly_charts = strip_legacy_charts
weekly_markdown_to_email_text = markdown_to_email_text


def weekly_markdown_to_email_html(markdown: str, *, title: str = "週次サマリー") -> str:
    return markdown_to_email_html(markdown, title=title)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEEKLY_DIR = _REPO_ROOT / "docs" / "summaries" / "weekly"


def load_weekly_email_bodies(
    iso_week: str,
    *,
    weekly_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    """週次 Markdown から (text, html) を返す。ファイルが無ければ FileNotFoundError。"""
    path = (weekly_dir or _WEEKLY_DIR) / f"{iso_week}.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    return weekly_markdown_to_email_text(raw), weekly_markdown_to_email_html(
        raw, title=f"週次サマリー — {iso_week}"
    )
