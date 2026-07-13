"""サマリー Web ページ用: 日次・週次 Markdown からプレビュー/全文の構造を組み立てる。

方針（案1: ティーザー公開）:
- Web はプレビュー範囲のみ表示（日次=一行結論＋動いた3つ、週次=流れ＋動いた話題各1）
- 全文（カテゴリ別・順位推移・週内推移）はメール配信の領分なので、ここでは
  「ロックされたセクション見出し」だけを返し、本文は出さない。

原稿の正本・保持・レビュー gate は docs/summaries/README.md を参照。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from markupsafe import Markup, escape

JST = timezone(timedelta(hours=9))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAILY_DIR = _REPO_ROOT / "docs" / "summaries" / "daily"
_WEEKLY_DIR = _REPO_ROOT / "docs" / "summaries" / "weekly"

_DAILY_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEKLY_ID_RE = re.compile(r"^\d{4}-W\d{2}$")

# インライン Markdown（リンク・太字）だけを HTML 化する。原稿は AI 生成＋レビュー済みの
# 管理下コンテンツだが、念のため escape してからリンク/太字のみ復元する。
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def render_inline(text: str) -> Markup:
    """リンクと太字のみを安全に HTML 化する。"""
    escaped = str(escape(text or ""))

    def _link(m: "re.Match[str]") -> str:
        label, url = m.group(1), m.group(2)
        if not url.startswith(("http://", "https://")):
            return label
        return f'<a href="{url}" target="_blank" rel="noopener nofollow">{label}</a>'

    escaped = _LINK_RE.sub(_link, escaped)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return Markup(escaped)


def _split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            return text[3:end].strip("\n"), text[end + 4 :]
    return "", text


def _parse_frontmatter(fm: str) -> dict:
    out: dict = {}
    for line in fm.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        out[key] = value
    return out


def _parse_slots(fm: str) -> tuple[str, ...]:
    m = re.search(r"snapshot_slots_included:\s*\[(.*?)\]", fm)
    if not m:
        return ()
    return tuple(
        s.strip().strip('"').strip("'") for s in m.group(1).split(",") if s.strip()
    )


def _split_sections(body: str, prefix: str) -> list[tuple[str, str]]:
    """``prefix``（例 ``"## "``）で始まる見出し単位に分割する。"""
    sections: list[tuple[str, str]] = []
    title: Optional[str] = None
    buf: list[str] = []
    for line in body.splitlines():
        if line.startswith(prefix) and not line[len(prefix) :].startswith("#"):
            if title is not None:
                sections.append((title, "\n".join(buf)))
            title = line[len(prefix) :].strip()
            buf = []
        elif title is not None:
            buf.append(line)
    if title is not None:
        sections.append((title, "\n".join(buf)))
    return sections


def _find_section(sections: list[tuple[str, str]], *keywords: str) -> str:
    for title, content in sections:
        if any(k in title for k in keywords):
            return content
    return ""


def _clean_title(title: str) -> str:
    """見出しから日付サフィックス（``— 2026-07-11`` 等）だけを除く。

    週次の ``カテゴリ別 — 今週の top3`` のような説明サフィックスは残す。
    """
    return re.sub(r"\s*—\s*\d{4}[-/].*$", "", title).strip()


def _join_paragraph(content: str) -> str:
    lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
    return " ".join(lines).strip()


def _split_sentences(text: str) -> list[str]:
    """句点「。」で文単位に分割（句点は各文末に残す）。長い一行結論を読みやすく改行するための表示用。"""
    s = (text or "").strip()
    if not s:
        return []
    return [part.strip() for part in re.split(r"(?<=。)", s) if part.strip()]


# 本文中の markdown リンク行 [ラベル](http...) からトピック名とURLを拾うための正規表現。
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def _collect_topic_links(body: str) -> list[tuple[str, str]]:
    """本文全体の [ラベル](url) を集め、一行結論のリンク化に使う (ラベル, url) 一覧を返す。

    同じラベルは最初の URL を採用。長いラベルを優先マッチさせたいので長さ降順で返す。
    """
    seen: dict[str, str] = {}
    for label, url in _MD_LINK_RE.findall(body):
        label = label.strip()
        # 1文字ラベルは誤マッチしやすいので除外
        if len(label) >= 2 and label not in seen:
            seen[label] = url
    return sorted(seen.items(), key=lambda kv: len(kv[0]), reverse=True)


def _linkify(text: str, links: list[tuple[str, str]]) -> Markup:
    """text 中に現れる既知トピック名だけを安全にリンク化する（longest-match・全文 escape 済み）。"""
    if not text:
        return Markup("")
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        for label, url in links:
            if text.startswith(label, i):
                safe_url = str(escape(url))
                safe_label = str(escape(label))
                out.append(
                    f'<a href="{safe_url}" target="_blank" rel="noopener nofollow">{safe_label}</a>'
                )
                i += len(label)
                break
        else:
            out.append(str(escape(text[i])))
            i += 1
    return Markup("".join(out))


def _publishable(status: str, *, allow_draft: bool) -> bool:
    st = (status or "draft").strip().lower()
    if st == "approved":
        return True
    return allow_draft and st == "draft"


def _jp_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def _iso_week_id(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


# --- 日次 ---------------------------------------------------------------

def _parse_daily_rising(content: str) -> list[dict]:
    items: list[dict] = []
    cur: Optional[dict] = None
    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue
        head = re.match(r"^\d+\.\s+(.*)$", s)
        if head:
            if cur:
                items.append(cur)
            link = re.match(r"^\[(.+?)\]\((.+?)\)（(.+)）$", head.group(1))
            if link:
                title, url, source = link.group(1), link.group(2), link.group(3)
                cur = {
                    "title_html": render_inline(f"[{title}]({url})"),
                    "source": source,
                    "note": "",
                }
            else:
                cur = {
                    "title_html": Markup(str(escape(head.group(1)))),
                    "source": "",
                    "note": "",
                }
            continue
        note = re.match(r"^-\s*\*\*補足\*\*[:：]\s*(.*)$", s)
        if note and cur is not None:
            cur["note"] = note.group(1).strip()
    if cur:
        items.append(cur)
    return items


def load_daily_page(date_str: str, *, allow_draft: bool = False) -> Optional[dict]:
    if not _DAILY_DATE_RE.match(date_str or ""):
        return None
    path = _DAILY_DIR / f"{date_str}.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, body = _split_frontmatter(text)
    meta = _parse_frontmatter(fm)
    if meta.get("generator") != "openai":
        return None
    status = meta.get("status", "draft")
    if not _publishable(status, allow_draft=allow_draft):
        return None
    try:
        business_day = date.fromisoformat(meta.get("business_day") or date_str)
    except ValueError:
        return None

    sections = _split_sections(body, "## ")
    one_liner = _join_paragraph(_find_section(sections, "一行結論"))
    # 本文中のリンクを対応表にして、一行結論のトピック名にリンクを張る
    topic_links = _collect_topic_links(body)
    one_liner_sentences = [_linkify(s, topic_links) for s in _split_sentences(one_liner)]
    rising = _parse_daily_rising(_find_section(sections, "いちばん動いた"))
    locked = [
        _clean_title(title)
        for title, _ in sections
        if not ("一行結論" in title or "いちばん動いた" in title)
    ]

    week_id = _iso_week_id(business_day)
    return {
        "kind": "daily",
        "business_day": business_day.isoformat(),
        "business_day_display": _jp_date(business_day),
        "generated_at": meta.get("generated_at", ""),
        "status": status,
        "slots": list(_parse_slots(fm) or ("07", "13", "19", "01")),
        "one_liner": one_liner,
        "one_liner_sentences": one_liner_sentences,
        "rising": rising,
        "locked_sections": locked,
        "week_id": week_id,
        "week_available": weekly_available(week_id, allow_draft=allow_draft),
    }


# --- 週次 ---------------------------------------------------------------

def _parse_weekly_rising_item(content: str) -> Optional[dict]:
    lines = content.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        m = re.match(r"^\d+\.\s+\[(.+?)\]\((.+?)\)（(.+)）\s*$", s)
        if not m:
            continue
        title, url, source = m.group(1), m.group(2), m.group(3)
        move = ""
        for nxt in lines[i + 1 :]:
            ns = nxt.strip()
            if ns.startswith(">"):
                move = ns.lstrip(">").strip()
                break
            if re.match(r"^\d+\.", ns) or ns.startswith("#"):
                break
        return {
            "title_html": render_inline(f"[{title}]({url})"),
            "source": source,
            "move_html": render_inline(move),
        }
    return None


def load_weekly_page(week_id: str, *, allow_draft: bool = False) -> Optional[dict]:
    if not _WEEKLY_ID_RE.match(week_id or ""):
        return None
    path = _WEEKLY_DIR / f"{week_id}.md"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    fm, body = _split_frontmatter(text)
    meta = _parse_frontmatter(fm)
    if meta.get("generator") != "openai":
        return None
    status = meta.get("status", "draft")
    if not _publishable(status, allow_draft=allow_draft):
        return None

    sections = _split_sections(body, "## ")
    flow_section = _find_section(sections, "今週の流れ")
    flow_subs = _split_sections(flow_section, "### ")
    flow = {
        "jp": render_inline(_join_paragraph(_find_section(flow_subs, "日本"))),
        "us": render_inline(_join_paragraph(_find_section(flow_subs, "アメリカ", "US"))),
    }

    rising_section = _find_section(sections, "いちばん動いた")
    rising_subs = _split_sections(rising_section, "### ")
    rising = {
        "jp": _parse_weekly_rising_item(_find_section(rising_subs, "日本")),
        "us": _parse_weekly_rising_item(_find_section(rising_subs, "アメリカ", "US")),
    }

    locked = [
        _clean_title(title)
        for title, _ in sections
        if not ("今週の流れ" in title or "いちばん動いた" in title)
    ]

    return {
        "kind": "weekly",
        "iso_week": meta.get("iso_week", week_id),
        "week_range": meta.get("week_range_jst", ""),
        "generated_at": meta.get("generated_at", ""),
        "status": status,
        "flow": flow,
        "rising": rising,
        "locked_sections": locked,
    }


def weekly_available(week_id: str, *, allow_draft: bool = False) -> bool:
    if not _WEEKLY_ID_RE.match(week_id or ""):
        return False
    path = _WEEKLY_DIR / f"{week_id}.md"
    if not path.is_file():
        return False
    try:
        fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    meta = _parse_frontmatter(fm)
    if meta.get("generator") != "openai":
        return False
    return _publishable(meta.get("status", "draft"), allow_draft=allow_draft)


# --- 一覧（sitemap 用） -------------------------------------------------

def list_published_daily(*, allow_draft: bool = False) -> list[tuple[str, datetime]]:
    """公開可能な日次 (date_str, lastmod) を新しい順で返す。"""
    return _list_published(_DAILY_DIR, _DAILY_DATE_RE, allow_draft=allow_draft)


def list_published_weekly(*, allow_draft: bool = False) -> list[tuple[str, datetime]]:
    return _list_published(_WEEKLY_DIR, _WEEKLY_ID_RE, allow_draft=allow_draft)


def _weekly_display(week_id: str) -> str:
    """``2026-W28`` → ``2026年 第28週``。パースできなければそのまま返す。"""
    m = _WEEKLY_ID_RE.match(week_id or "")
    if not m:
        return week_id
    year, week = week_id.split("-W")
    return f"{year}年 第{int(week)}週"


def _daily_display(date_str: str) -> str:
    try:
        return _jp_date(date.fromisoformat(date_str))
    except ValueError:
        return date_str


def _neighbor_ids(ids: list[str], current_id: str) -> tuple[Optional[str], Optional[str]]:
    """新しい順に並んだ ID 一覧から (older, newer) を返す。current が無ければ (None, None)。"""
    if current_id not in ids:
        return None, None
    idx = ids.index(current_id)
    newer = ids[idx - 1] if idx > 0 else None
    older = ids[idx + 1] if idx + 1 < len(ids) else None
    return older, newer


def daily_neighbors(date_str: str, *, allow_draft: bool = False) -> dict:
    """指定日の前後（保持期間内に公開されている隣接分のみ）を返す。

    older = より古い日付 / newer = より新しい日付。欠けている日は飛ばして
    「実際に閲覧できる隣接分」を指すので、連続した暦日とは限らない。
    """
    ids = [d for d, _ in list_published_daily(allow_draft=allow_draft)]
    older_id, newer_id = _neighbor_ids(ids, date_str)

    def _mk(i: Optional[str]) -> Optional[dict]:
        if not i:
            return None
        return {"id": i, "display": _daily_display(i), "url": f"/summaries/daily/{i}"}

    return {"older": _mk(older_id), "newer": _mk(newer_id)}


def weekly_neighbors(week_id: str, *, allow_draft: bool = False) -> dict:
    """指定週の前後（保持期間内に公開されている隣接分のみ）を返す。"""
    ids = [w for w, _ in list_published_weekly(allow_draft=allow_draft)]
    older_id, newer_id = _neighbor_ids(ids, week_id)

    def _mk(i: Optional[str]) -> Optional[dict]:
        if not i:
            return None
        return {"id": i, "display": _weekly_display(i), "url": f"/summaries/weekly/{i}"}

    return {"older": _mk(older_id), "newer": _mk(newer_id)}


def build_summary_index(*, allow_draft: bool = False) -> dict:
    """一覧ページ用に、公開中の日次・週次サマリーの見出し情報を新しい順で返す。

    保持期間（日次10日・週次30日が既定）を過ぎた原稿はファイルごと削除されるため、
    ここに並ぶのは「いま閲覧できる直近分」だけ。制限は呼び出し側で明示する。
    """
    daily: list[dict] = []
    for date_str, _ in list_published_daily(allow_draft=allow_draft):
        page = load_daily_page(date_str, allow_draft=allow_draft)
        if not page:
            continue
        daily.append(
            {
                "id": date_str,
                "display": page["business_day_display"],
                "one_liner": page["one_liner"],
                "url": f"/summaries/daily/{date_str}",
            }
        )

    weekly: list[dict] = []
    for week_id, _ in list_published_weekly(allow_draft=allow_draft):
        page = load_weekly_page(week_id, allow_draft=allow_draft)
        if not page:
            continue
        weekly.append(
            {
                "id": week_id,
                "display": _weekly_display(week_id),
                "week_range": page.get("week_range", ""),
                "url": f"/summaries/weekly/{week_id}",
            }
        )

    return {"daily": daily, "weekly": weekly}


def _list_published(
    directory: Path, id_re: "re.Pattern[str]", *, allow_draft: bool
) -> list[tuple[str, datetime]]:
    if not directory.is_dir():
        return []
    out: list[tuple[str, datetime]] = []
    for path in directory.glob("*.md"):
        stem = path.stem
        if not id_re.match(stem):
            continue
        try:
            fm, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        meta = _parse_frontmatter(fm)
        if meta.get("generator") != "openai":
            continue
        if not _publishable(meta.get("status", "draft"), allow_draft=allow_draft):
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=JST)
        out.append((stem, mtime))
    out.sort(key=lambda t: t[0], reverse=True)
    return out
