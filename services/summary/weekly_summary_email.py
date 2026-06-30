"""週次サマリーのメール本文（HTML / テキスト）。画像・添付なし。"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEEKLY_DIR = _REPO_ROOT / "docs" / "summaries" / "weekly"
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_IMAGE_LINE_RE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*\n?", re.MULTILINE)
_MERMAID_BLOCK_RE = re.compile(r"```mermaid[\s\S]*?```\s*\n?", re.MULTILINE)
_SVG_BLOCK_RE = re.compile(r"<svg[\s\S]*?</svg>\s*\n?", re.MULTILINE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def strip_legacy_weekly_charts(markdown: str) -> str:
    """Mermaid / SVG / 画像参照を除去し、表とテキスト推移だけ残す。"""
    text = markdown
    text = _MERMAID_BLOCK_RE.sub("", text)
    text = _SVG_BLOCK_RE.sub("", text)
    text = _IMAGE_LINE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def strip_front_matter(markdown: str) -> str:
    return _FRONTMATTER_RE.sub("", markdown, count=1)


def weekly_markdown_to_email_text(markdown: str) -> str:
    """配信用プレーンテキスト（添付なし）。"""
    body = strip_legacy_weekly_charts(strip_front_matter(markdown))
    body = _LINK_RE.sub(r"\1 (\2)", body)
    body = _BOLD_RE.sub(r"\1", body)
    return body.strip() + "\n"


def weekly_markdown_to_email_html(markdown: str, *, title: str = "週次サマリー") -> str:
    """配信用 HTML（インライン画像・添付なし）。"""
    text = weekly_markdown_to_email_text(markdown)
    parts: list[str] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("|"):
            if not in_table:
                parts.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            tag = "th" if not parts or parts[-1] == "<table>" else "td"
            if tag == "th":
                parts.append("<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cells) + "</tr>")
            else:
                parts.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            parts.append("</table>")
            in_table = False
        if line.startswith("> "):
            parts.append(f"<p><em>{html.escape(line[2:])}</em></p>")
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            content = line.lstrip("#").strip()
            parts.append(f"<h{min(level, 4)}>{html.escape(content)}</h{min(level, 4)}>")
        elif line.strip():
            parts.append(f"<p>{html.escape(line)}</p>")
        else:
            parts.append("")
    if in_table:
        parts.append("</table>")
    inner = "\n".join(parts)
    safe_title = html.escape(title)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title></head><body>"
        f"<h1>{safe_title}</h1>\n{inner}\n</body></html>"
    )


def load_weekly_email_bodies(
    iso_week: str,
    *,
    weekly_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    """承認済み週次 Markdown から (text, html) を返す。ファイルが無ければ FileNotFoundError。"""
    path = (weekly_dir or _WEEKLY_DIR) / f"{iso_week}.md"
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    return weekly_markdown_to_email_text(raw), weekly_markdown_to_email_html(
        raw, title=f"週次サマリー — {iso_week}"
    )
