"""サマリー Markdown → メール本文（HTML / テキスト）。画像・添付なし。

日次・週次共通。レガシーの Mermaid / SVG / 画像参照は除去する。
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUMMARIES_ROOT = _REPO_ROOT / "docs" / "summaries"

WORLD_FRONT_PAGE_BASE = "https://g7-dashboard.vercel.app/"
_DEFAULT_SITE_BASE_URL = "https://trends-dashboard.com"
_EMAIL_LINK_STYLE = "color:#0d6efd;text-decoration:underline;"

_FOOTER_COPY = {
    "jp": {
        "dashboard_text": "ダッシュボードで最新データを見る\n{url}",
        "dashboard_label": "ダッシュボードで最新データを見る",
        "related_text": "関連: 世界9カ国のニュース表紙 → World Front Page\n{url}",
        "related_html": "関連: {link} — G7・中国・インドの主要メディア表紙見出し",
    },
    "us": {
        "dashboard_text": "See the latest on the dashboard\n{url}",
        "dashboard_label": "See the latest on the dashboard",
        "related_text": "Related: Top headlines from G7 countries → World Front Page\n{url}",
        "related_html": "Related: {link} — Top headlines from G7, China & India",
    },
}

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
_IMAGE_LINE_RE = re.compile(r"^!\[[^\]]*\]\([^)]+\)\s*\n?", re.MULTILINE)
_MERMAID_BLOCK_RE = re.compile(r"```mermaid[\s\S]*?```\s*\n?", re.MULTILINE)
_SVG_BLOCK_RE = re.compile(r"<svg[\s\S]*?</svg>\s*\n?", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
# ](http…) を錨にし、ラベル内の ] や \[ エスケープにも耐える
_MD_LINK_HREF_RE = re.compile(r"\]\((https?://[^)\s]+|mailto:[^)\s]+)\)")

# 既存原稿の Google 検索フォールバックがタイトル全文を載せている場合の肥大化防止
_EMAIL_SEARCH_Q_MAX = 48


def _find_md_link_open(text: str, close_idx: int) -> int:
    """`](url)` の `]` 位置から、対応する開き `[` を探す（`\\[` は無視）。"""
    i = close_idx - 1
    while i >= 0:
        if text[i] == "[":
            if i > 0 and text[i - 1] == "\\":
                i -= 2
                continue
            return i
        i -= 1
    return -1


def iter_markdown_links(text: str):
    """Yield (start, end, label, url)。ラベル内に `]` があっても可。"""
    for m in _MD_LINK_HREF_RE.finditer(text):
        close_idx = m.start()
        open_idx = _find_md_link_open(text, close_idx)
        if open_idx < 0:
            continue
        label = text[open_idx + 1 : close_idx]
        label = label.replace("\\[", "[").replace("\\]", "]")
        yield open_idx, m.end(), label, m.group(1)


def shorten_email_href(url: str, *, max_q: int = _EMAIL_SEARCH_Q_MAX) -> str:
    """過長な google.com/search?q=… の q だけ短縮する（他 URL はそのまま）。"""
    s = (url or "").strip()
    if not s.startswith(("http://", "https://")):
        return s
    try:
        p = urlparse(s)
    except ValueError:
        return s
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host != "google.com" or (p.path or "").rstrip("/") != "/search":
        return s
    qs = parse_qs(p.query, keep_blank_values=True)
    q_vals = qs.get("q") or []
    if not q_vals:
        return s
    q = q_vals[0]
    if len(q) <= max_q:
        return s
    cut = q[:max_q].rstrip()
    for sep in ("！", "!", "。", " ", "　", "・", "｜", "|", "【"):
        idx = cut.rfind(sep)
        if idx >= max(12, max_q // 3):
            cut = cut[:idx].rstrip()
            break
    qs["q"] = [cut]
    flat: list[tuple[str, str]] = []
    for key, vals in qs.items():
        for v in vals:
            flat.append((key, v))
    new_query = urlencode(flat, quote_via=quote_plus)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


_CATEGORY_TREND_LINE_RE = re.compile(
    r"^\*\*(?:昨日の傾向|Yesterday's trend)\*\*:.*\n?",
    re.MULTILINE,
)
# 既存原稿のメタ行（タイトルと重複・またはプレースホルダ）
_HEADER_META_LINE_RE = re.compile(
    r"^- \*\*(?:対象（観測日）|Observation day|生成・送信完了|Generated)\*\*:.*\n?",
    re.MULTILINE,
)


def strip_category_trend_blurbs(markdown: str) -> str:
    """既存原稿の「昨日の傾向」行を除去（カテゴリ間で有無がバラつくため）。"""
    text = _CATEGORY_TREND_LINE_RE.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_redundant_header_meta(markdown: str) -> str:
    """観測日・生成時刻のメタ箇条書きを除去（メール見出しと重複するため）。"""
    text = _HEADER_META_LINE_RE.sub("", markdown)
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_legacy_charts(markdown: str) -> str:
    """Mermaid / SVG / 画像参照を除去し、表とテキスト推移だけ残す。"""
    text = markdown
    text = _MERMAID_BLOCK_RE.sub("", text)
    text = _SVG_BLOCK_RE.sub("", text)
    text = _IMAGE_LINE_RE.sub("", text)
    text = strip_category_trend_blurbs(text)
    text = strip_redundant_header_meta(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def strip_front_matter(markdown: str) -> str:
    return _FRONTMATTER_RE.sub("", markdown, count=1)


def markdown_to_email_text(markdown: str) -> str:
    """配信用プレーンテキスト（添付なし）。"""
    body = strip_legacy_charts(strip_front_matter(markdown))

    def _expand_link_region(s: str) -> str:
        parts: list[str] = []
        pos = 0
        for start, end, label, href in iter_markdown_links(s):
            parts.append(s[pos:start])
            # HTML パートが本リンク。テキストはラベルのみ（長い URL を晒さない）
            parts.append(label)
            pos = end
        parts.append(s[pos:])
        return "".join(parts)

    body = _expand_link_region(body)
    body = _BOLD_RE.sub(r"\1", body)
    # 長い段落（先週の流れなど）は句点・ピリオド後で改行
    lines: list[str] = []
    table_buf: list[list[str]] = []

    def _flush_table() -> None:
        nonlocal table_buf
        if not table_buf:
            return
        # 区切り行を除き、空角セルはスペースにして列を揃える
        rows = [
            [(" " if not c else c) for c in row]
            for row in table_buf
            if not all(set(c) <= {"-", ":", ""} for c in row)
        ]
        if rows:
            widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
            for row in rows:
                # 列数が欠けている行は埋めない（壊れた表はそのまま）
                if len(row) != len(widths):
                    lines.append("  ".join(row))
                    continue
                lines.append(
                    "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
                )
        table_buf = []

    for line in body.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_buf.append(cells)
            continue
        _flush_table()
        if line.startswith(("#", ">", "-", "*")) or re.match(r"^\d+\.\s", line):
            lines.append(line)
        elif line.strip():
            lines.append(_insert_sentence_breaks_text(line))
        else:
            lines.append(line)
    _flush_table()
    return "\n".join(lines).strip() + "\n"


# 英文ピリオド: 数字直後（1. や 7.5）は除外。空白＋続きがあるときだけ
_EN_SENTENCE_END_RE = re.compile(r"(?<!\d)\.(?=\s+\S)")
_INLINE_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _insert_sentence_breaks_text(text: str) -> str:
    """句点・文末ピリオドの後に改行を入れる（プレーンテキスト）。"""
    out = text.replace("。", "。\n")
    out = _EN_SENTENCE_END_RE.sub(".\n", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _insert_sentence_breaks_html(fragment: str) -> str:
    """句点・文末ピリオドの後に <br> を入れる（HTML 断片。タグ外のみ）。"""
    slots: list[str] = []

    def _park(m: re.Match[str]) -> str:
        slots.append(m.group(0))
        return f"\x00TAG{len(slots) - 1}\x00"

    parked = re.sub(r"<[^>]+>", _park, fragment)
    parked = parked.replace("。", "。<br>\n")
    parked = _EN_SENTENCE_END_RE.sub(".<br>\n", parked)
    parked = re.sub(r"(?:<br>\n)+$", "", parked)

    def _unpark(m: re.Match[str]) -> str:
        return slots[int(m.group(1))]

    return re.sub(r"\x00TAG(\d+)\x00", _unpark, parked)


def _inline_markdown_to_html(text: str) -> str:
    """インラインのリンク・太字を HTML にし、それ以外はエスケープ。"""
    # 先にリンクをプレースホルダ化し、ラベル内の ** や ] でも壊れないようにする
    slots: list[str] = []
    pieces: list[str] = []
    pos = 0
    for start, end, label, url in iter_markdown_links(text):
        pieces.append(text[pos:start])
        href = shorten_email_href(url.strip())
        if href.startswith(("http://", "https://", "mailto:")):
            slots.append(
                f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'
            )
        else:
            slots.append(html.escape(f"{label} ({href})"))
        pieces.append(f"\x00L{len(slots) - 1}\x00")
        pos = end
    pieces.append(text[pos:])
    interim = "".join(pieces)

    parts: list[str] = []
    pos = 0
    for m in _INLINE_BOLD_RE.finditer(interim):
        chunk = interim[pos : m.start()]
        parts.append(_escape_keeping_link_slots(chunk, slots))
        parts.append(f"<strong>{html.escape(m.group(1))}</strong>")
        pos = m.end()
    parts.append(_escape_keeping_link_slots(interim[pos:], slots))
    return "".join(parts)


def _escape_keeping_link_slots(text: str, slots: list[str]) -> str:
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\x00L(\d+)\x00", text):
        out.append(html.escape(text[pos : m.start()]))
        out.append(slots[int(m.group(1))])
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


_TABLE_STYLE = "border-collapse:collapse;margin:0.75em 0;"
_TH_STYLE = "border:1px solid #ccc;padding:4px 8px;text-align:center;background:#f7f7f7;"
_TD_STYLE = "border:1px solid #ccc;padding:4px 8px;text-align:center;"


def markdown_to_email_html(
    markdown: str,
    *,
    title: str = "サマリー",
    skip_first_h1: bool = True,
) -> str:
    """配信用 HTML（インライン画像・添付なし）。リンクは <a> にする。

    skip_first_h1: ラッパーの <h1>{title}</h1> と原稿先頭の # 見出しが二重になるのを防ぐ。
    """
    body = strip_legacy_charts(strip_front_matter(markdown))
    parts: list[str] = []
    in_table = False
    skipped_h1 = False
    for line in body.splitlines():
        if line.startswith("|"):
            if not in_table:
                parts.append(f'<table style="{_TABLE_STYLE}">')
                in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            tag = "th" if not parts or parts[-1].startswith("<table") else "td"
            cell_style = _TH_STYLE if tag == "th" else _TD_STYLE
            # 角セルが空でも列数を保つ（レイアウト崩れ防止）
            cell_html = []
            for c in cells:
                content = _inline_markdown_to_html(c) if c else "&nbsp;"
                cell_html.append(f'<{tag} style="{cell_style}">{content}</{tag}>')
            parts.append("<tr>" + "".join(cell_html) + "</tr>")
            continue
        if in_table:
            parts.append("</table>")
            in_table = False
        if line.startswith("> "):
            inner = _insert_sentence_breaks_html(_inline_markdown_to_html(line[2:]))
            parts.append(f"<p><em>{inner}</em></p>")
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            content = line.lstrip("#").strip()
            # 原稿の先頭 H1（例: # 日次サマリー — …（JST））はラッパー title と重複するので省略
            if (
                skip_first_h1
                and not skipped_h1
                and level == 1
                and not any(p.startswith("<h") or p.startswith("<p") or p.startswith("<table") for p in parts)
            ):
                skipped_h1 = True
                continue
            parts.append(
                f"<h{min(level, 4)}>{_inline_markdown_to_html(content)}</h{min(level, 4)}>"
            )
        elif line.strip():
            # 番号付きリスト行は文分割しない（"1. タイトル" を壊さない）
            if re.match(r"^\d+\.\s", line) or line.lstrip().startswith(("- ", "* ")):
                parts.append(f"<p>{_inline_markdown_to_html(line)}</p>")
            else:
                inner = _insert_sentence_breaks_html(_inline_markdown_to_html(line))
                parts.append(f"<p>{inner}</p>")
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


def _public_base_url() -> str:
    return (
        os.getenv("PUBLIC_BASE_URL")
        or os.getenv("TREND_DASHBOARD_BASE_URL")
        or _DEFAULT_SITE_BASE_URL
    ).strip().rstrip("/")


def _footer_utm(*, region: str, kind: str) -> str:
    return urlencode(
        {
            "utm_source": "trends_dashboard",
            "utm_medium": "summary_email",
            "utm_campaign": region,
            "utm_content": kind,
        }
    )


def _email_anchor(url: str, label: str) -> str:
    return (
        f'<a href="{html.escape(url, quote=True)}" style="{_EMAIL_LINK_STYLE}">'
        f"{html.escape(label)}</a>"
    )


def dashboard_email_url(*, region: str, kind: str) -> str:
    """サマリーメールフッター用の Trend Dashboard URL（効果測定用 UTM 付き）。"""
    region_n = (region or "jp").strip().lower()
    kind_n = (kind or "daily").strip().lower()
    base = _public_base_url()
    path = "/us" if region_n == "us" else "/"
    return f"{base}{path}?{_footer_utm(region=region_n, kind=kind_n)}"


def world_front_page_email_url(*, region: str, kind: str) -> str:
    """サマリーメールフッター用の World Front Page URL（効果測定用 UTM 付き）。"""
    region_n = (region or "jp").strip().lower()
    kind_n = (kind or "daily").strip().lower()
    return f"{WORLD_FRONT_PAGE_BASE}?{_footer_utm(region=region_n, kind=kind_n)}"


def append_summary_email_footer(
    text: str,
    html_body: str,
    *,
    region: str,
    kind: str,
) -> Tuple[str, str]:
    """配信メール末尾に Trend Dashboard と World Front Page へのリンクを付ける。"""
    region_n = (region or "jp").strip().lower()
    if region_n not in _FOOTER_COPY:
        region_n = "jp"
    dash_url = dashboard_email_url(region=region_n, kind=kind)
    wfp_url = world_front_page_email_url(region=region_n, kind=kind)
    copy = _FOOTER_COPY[region_n]
    text_out = (
        text.rstrip()
        + "\n\n---\n"
        + copy["dashboard_text"].format(url=dash_url)
        + "\n\n"
        + copy["related_text"].format(url=wfp_url)
        + "\n"
    )
    dash_link = _email_anchor(dash_url, copy["dashboard_label"])
    wfp_link = _email_anchor(wfp_url, "World Front Page")
    footer_html = (
        '<hr style="border:none;border-top:1px solid #ddd;margin:2em 0 1em;">'
        f'<p style="font-size:0.9em;margin:0 0 0.75em;">{dash_link}</p>'
        f'<p style="font-size:0.9em;color:#666;margin:0;">'
        f"{copy['related_html'].format(link=wfp_link)}"
        "</p>"
    )
    if "</body>" in html_body:
        html_out = html_body.replace("</body>", f"{footer_html}\n</body>", 1)
    else:
        html_out = html_body.rstrip() + "\n" + footer_html
    return text_out, html_out


def summary_markdown_path(
    kind: str,
    doc_id: str,
    *,
    region: str = "jp",
    summaries_root: Optional[Path] = None,
) -> Path:
    """日次/週次 Markdown のパス（JP は直下、US は us/）。"""
    root = summaries_root or _SUMMARIES_ROOT
    region = (region or "jp").strip().lower()
    kind = (kind or "").strip().lower()
    if kind == "daily":
        base = root / "daily"
        return (base / doc_id).with_suffix(".md") if region == "jp" else base / region / f"{doc_id}.md"
    if kind == "weekly":
        base = root / "weekly"
        return (base / doc_id).with_suffix(".md") if region == "jp" else base / region / f"{doc_id}.md"
    raise ValueError(f"unsupported kind: {kind}")


def summary_email_heading(kind: str, doc_id: str, region: str = "jp") -> str:
    """メール HTML の <title>/<h1>。原稿先頭 H1 は省略するので地域の言語に合わせる。"""
    region_u = (region or "jp").strip().upper() or "JP"
    kind = (kind or "").strip().lower()
    if region_u == "US":
        if kind == "weekly":
            return f"Weekly summary — {doc_id} (US)"
        return f"Daily summary — {doc_id} (US)"
    if kind == "weekly":
        return f"週次サマリー — {doc_id} ({region_u})"
    return f"日次サマリー — {doc_id} ({region_u})"


def load_summary_email_bodies(
    kind: str,
    doc_id: str,
    *,
    region: str = "jp",
    summaries_root: Optional[Path] = None,
    title: Optional[str] = None,
) -> Tuple[Path, str, str]:
    """Markdown から (path, text, html) を返す。無ければ FileNotFoundError。"""
    path = summary_markdown_path(
        kind, doc_id, region=region, summaries_root=summaries_root
    )
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = path.read_text(encoding="utf-8")
    if title is None:
        title = summary_email_heading(kind, doc_id, region)
    text = markdown_to_email_text(raw)
    html_body = markdown_to_email_html(raw, title=title)
    text, html_body = append_summary_email_footer(
        text, html_body, region=region, kind=kind
    )
    return path, text, html_body
