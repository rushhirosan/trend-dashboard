"""サマリー Web ページ用: 日次・週次 Markdown からプレビュー/全文の構造を組み立てる。

方針（案1: ティーザー公開）:
- Web はプレビュー範囲のみ表示（日次=一行結論＋動いた3つ、週次=流れ＋動いた話題各1）
- 全文（読み方メモ・カテゴリ別・順位推移・週内推移）はメール配信の領分なので、ここでは
  「ロックされたセクション見出し」だけを返し、本文は出さない。

原稿の読み込みは DB（summary_documents・GHA が毎朝 upsert）を優先し、
無ければリポジトリ内ファイル（deploy 時点のスナップショット）へフォールバック
する。イメージに残った保持期間超過ファイルを出さないよう、一覧・詳細とも
保持期間カットオフでフィルタする。

原稿の正本・保持・レビュー gate は docs/summaries/README.md を参照。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from markupsafe import Markup, escape

from services.summary import summary_store

JST = timezone(timedelta(hours=9))

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAILY_DIR = _REPO_ROOT / "docs" / "summaries" / "daily"
_WEEKLY_DIR = _REPO_ROOT / "docs" / "summaries" / "weekly"

_DAILY_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_WEEKLY_ID_RE = re.compile(r"^\d{4}-W\d{2}$")

# --- リージョン ---------------------------------------------------------
# JP は従来どおり docs/summaries/{daily,weekly}/ 直下、US は its us/ サブディレクトリ。
# URL も JP は /summaries/...、US は /us/summaries/... と接頭辞を付ける。
REGIONS = ("jp", "us")

_EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _norm_region(region: Optional[str]) -> str:
    r = (region or "jp").strip().lower()
    return r if r in REGIONS else "jp"


def _daily_dir(region: str) -> Path:
    return _DAILY_DIR if region == "jp" else _DAILY_DIR / region


def _weekly_dir(region: str) -> Path:
    return _WEEKLY_DIR if region == "jp" else _WEEKLY_DIR / region


def _url_prefix(region: str) -> str:
    return "" if region == "jp" else f"/{region}"


# --- 原稿の読み込み（DB 優先・ファイル fallback） -----------------------

def _within_retention(kind: str, doc_id: str, *, today: Optional[date] = None) -> bool:
    """保持期間内の原稿か。イメージ焼き込みで残った古いファイルの表示を防ぐ。"""
    from services.snapshot_retention import (
        daily_summary_cutoff_business_day,
        weekly_summary_cutoff,
    )

    if kind == "daily":
        try:
            d = date.fromisoformat(doc_id)
        except ValueError:
            return False
        return d >= daily_summary_cutoff_business_day(today=today)
    monday = summary_store.weekly_monday(doc_id)
    if monday is None:
        return False
    return monday >= weekly_summary_cutoff(today=today)


def _doc_dir(kind: str, region: str) -> Path:
    return _daily_dir(region) if kind == "daily" else _weekly_dir(region)


def _read_doc(kind: str, region: str, doc_id: str) -> Optional[str]:
    """原稿本文を返す。DB（summary_documents）優先・リポジトリ内ファイル fallback。"""
    text = summary_store.get_document(kind, region, doc_id)
    if text is not None:
        return text
    path = _doc_dir(kind, region) / f"{doc_id}.md"
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


# 見出しの言語差を吸収するためのキーワード（JP/EN 両対応）。
# US 原稿は英語見出しで生成する想定だが、パーサはどちらでも拾えるようにする。
_ONE_LINER_KEYS = ("昨日の注目", "一行結論", "highlight", "takeaway", "bottom line")
_RISING_KEYS = ("いちばん動いた", "biggest movers", "movers")
_FLOW_KEYS = ("今週の流れ", "week in review", "this week")
_JP_SUB_KEYS = ("日本", "Japan", "JP")
_US_SUB_KEYS = ("アメリカ", "US", "United States")


def _title_has(title: str, *keywords: str) -> bool:
    t = title.lower()
    return any(k.lower() in t for k in keywords)

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
    lowered = [k.lower() for k in keywords]
    for title, content in sections:
        t = title.lower()
        if any(k in t for k in lowered):
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


def _en_date(d: date) -> str:
    return f"{_EN_MONTHS[d.month - 1]} {d.day}, {d.year}"


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
        note = re.match(r"^-\s*\*\*(?:補足|Note)\*\*[:：]\s*(.*)$", s)
        if note and cur is not None:
            cur["note"] = note.group(1).strip()
    if cur:
        items.append(cur)
    return items


def load_daily_page(
    date_str: str, *, region: str = "jp", allow_draft: bool = False
) -> Optional[dict]:
    region = _norm_region(region)
    if not _DAILY_DATE_RE.match(date_str or ""):
        return None
    if not _within_retention("daily", date_str):
        return None
    text = _read_doc("daily", region, date_str)
    if text is None:
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
    one_liner = _join_paragraph(_find_section(sections, *_ONE_LINER_KEYS))
    # 本文中のリンクを対応表にして、一行結論のトピック名にリンクを張る
    topic_links = _collect_topic_links(body)
    one_liner_sentences = [_linkify(s, topic_links) for s in _split_sentences(one_liner)]
    rising = _parse_daily_rising(_find_section(sections, *_RISING_KEYS))
    locked = [
        _clean_title(title)
        for title, _ in sections
        if not _title_has(title, *_ONE_LINER_KEYS, *_RISING_KEYS)
    ]

    week_id = _iso_week_id(business_day)
    return {
        "kind": "daily",
        "region": region,
        "business_day": business_day.isoformat(),
        "business_day_display": _daily_display(business_day.isoformat(), region),
        "generated_at": meta.get("generated_at", ""),
        "status": status,
        "slots": list(_parse_slots(fm) or ("07", "13", "19", "01")),
        "one_liner": one_liner,
        "one_liner_sentences": one_liner_sentences,
        "rising": rising,
        "locked_sections": locked,
        "week_id": week_id,
        "week_available": weekly_available(week_id, region=region, allow_draft=allow_draft),
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


def load_weekly_page(
    week_id: str, *, region: str = "jp", allow_draft: bool = False
) -> Optional[dict]:
    region = _norm_region(region)
    if not _WEEKLY_ID_RE.match(week_id or ""):
        return None
    if not _within_retention("weekly", week_id):
        return None
    text = _read_doc("weekly", region, week_id)
    if text is None:
        return None
    fm, body = _split_frontmatter(text)
    meta = _parse_frontmatter(fm)
    if meta.get("generator") != "openai":
        return None
    status = meta.get("status", "draft")
    if not _publishable(status, allow_draft=allow_draft):
        return None

    sections = _split_sections(body, "## ")
    flow_section = _find_section(sections, *_FLOW_KEYS)
    flow_subs = _split_sections(flow_section, "### ")
    if flow_subs:
        flow = {
            "jp": render_inline(_join_paragraph(_find_section(flow_subs, *_JP_SUB_KEYS))),
            "us": render_inline(_join_paragraph(_find_section(flow_subs, *_US_SUB_KEYS))),
        }
    else:
        # 単一地域ファイル: 「今週の流れ」直下に本文（### なし）
        content = render_inline(_join_paragraph(flow_section))
        flow = {
            "jp": content if region == "jp" else Markup(""),
            "us": content if region == "us" else Markup(""),
        }

    rising_section = _find_section(sections, *_RISING_KEYS)
    rising_subs = _split_sections(rising_section, "### ")
    if rising_subs:
        rising = {
            "jp": _parse_weekly_rising_item(_find_section(rising_subs, *_JP_SUB_KEYS)),
            "us": _parse_weekly_rising_item(_find_section(rising_subs, *_US_SUB_KEYS)),
        }
    else:
        item = _parse_weekly_rising_item(rising_section)
        rising = {
            "jp": item if region == "jp" else None,
            "us": item if region == "us" else None,
        }

    locked = [
        _clean_title(title)
        for title, _ in sections
        if not _title_has(title, *_FLOW_KEYS, *_RISING_KEYS)
    ]

    return {
        "kind": "weekly",
        "region": region,
        "iso_week": meta.get("iso_week", week_id),
        "week_range": meta.get("week_range_jst") or meta.get("week_range", ""),
        "generated_at": meta.get("generated_at", ""),
        "status": status,
        "flow": flow,
        "rising": rising,
        "locked_sections": locked,
    }


def weekly_available(
    week_id: str, *, region: str = "jp", allow_draft: bool = False
) -> bool:
    region = _norm_region(region)
    if not _WEEKLY_ID_RE.match(week_id or ""):
        return False
    if not _within_retention("weekly", week_id):
        return False
    text = _read_doc("weekly", region, week_id)
    if text is None:
        return False
    fm, _ = _split_frontmatter(text)
    meta = _parse_frontmatter(fm)
    if meta.get("generator") != "openai":
        return False
    return _publishable(meta.get("status", "draft"), allow_draft=allow_draft)


# --- 一覧（sitemap 用） -------------------------------------------------

def list_published_daily(
    *, region: str = "jp", allow_draft: bool = False
) -> list[tuple[str, datetime]]:
    """公開可能な日次 (date_str, lastmod) を新しい順で返す。"""
    return _list_published("daily", _norm_region(region), allow_draft=allow_draft)


def list_published_weekly(
    *, region: str = "jp", allow_draft: bool = False
) -> list[tuple[str, datetime]]:
    return _list_published("weekly", _norm_region(region), allow_draft=allow_draft)


def _weekly_display(week_id: str, region: str = "jp") -> str:
    """``2026-W28`` → JP: ``2026年 第28週`` / US: ``2026 · Week 28``。"""
    m = _WEEKLY_ID_RE.match(week_id or "")
    if not m:
        return week_id
    year, week = week_id.split("-W")
    if region == "us":
        return f"{year} · Week {int(week)}"
    return f"{year}年 第{int(week)}週"


def _daily_display(date_str: str, region: str = "jp") -> str:
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return date_str
    return _en_date(d) if region == "us" else _jp_date(d)


def _neighbor_ids(ids: list[str], current_id: str) -> tuple[Optional[str], Optional[str]]:
    """新しい順に並んだ ID 一覧から (older, newer) を返す。current が無ければ (None, None)。"""
    if current_id not in ids:
        return None, None
    idx = ids.index(current_id)
    newer = ids[idx - 1] if idx > 0 else None
    older = ids[idx + 1] if idx + 1 < len(ids) else None
    return older, newer


def daily_neighbors(
    date_str: str, *, region: str = "jp", allow_draft: bool = False
) -> dict:
    """指定日の前後（保持期間内に公開されている隣接分のみ）を返す。

    older = より古い日付 / newer = より新しい日付。欠けている日は飛ばして
    「実際に閲覧できる隣接分」を指すので、連続した暦日とは限らない。
    """
    region = _norm_region(region)
    pfx = _url_prefix(region)
    ids = [d for d, _ in list_published_daily(region=region, allow_draft=allow_draft)]
    older_id, newer_id = _neighbor_ids(ids, date_str)

    def _mk(i: Optional[str]) -> Optional[dict]:
        if not i:
            return None
        return {"id": i, "display": _daily_display(i, region), "url": f"{pfx}/summaries/daily/{i}"}

    return {"older": _mk(older_id), "newer": _mk(newer_id)}


def weekly_neighbors(
    week_id: str, *, region: str = "jp", allow_draft: bool = False
) -> dict:
    """指定週の前後（保持期間内に公開されている隣接分のみ）を返す。"""
    region = _norm_region(region)
    pfx = _url_prefix(region)
    ids = [w for w, _ in list_published_weekly(region=region, allow_draft=allow_draft)]
    older_id, newer_id = _neighbor_ids(ids, week_id)

    def _mk(i: Optional[str]) -> Optional[dict]:
        if not i:
            return None
        return {"id": i, "display": _weekly_display(i, region), "url": f"{pfx}/summaries/weekly/{i}"}

    return {"older": _mk(older_id), "newer": _mk(newer_id)}


def build_summary_index(*, region: str = "jp", allow_draft: bool = False) -> dict:
    """一覧ページ用に、公開中の日次・週次サマリーの見出し情報を新しい順で返す。

    保持期間（日次10日・週次30日が既定）を過ぎた原稿はファイルごと削除されるため、
    ここに並ぶのは「いま閲覧できる直近分」だけ。制限は呼び出し側で明示する。
    """
    region = _norm_region(region)
    pfx = _url_prefix(region)
    daily: list[dict] = []
    for date_str, _ in list_published_daily(region=region, allow_draft=allow_draft):
        page = load_daily_page(date_str, region=region, allow_draft=allow_draft)
        if not page:
            continue
        daily.append(
            {
                "id": date_str,
                "display": page["business_day_display"],
                "one_liner": page["one_liner"],
                "url": f"{pfx}/summaries/daily/{date_str}",
            }
        )

    weekly: list[dict] = []
    for week_id, _ in list_published_weekly(region=region, allow_draft=allow_draft):
        page = load_weekly_page(week_id, region=region, allow_draft=allow_draft)
        if not page:
            continue
        weekly.append(
            {
                "id": week_id,
                "display": _weekly_display(week_id, region),
                "week_range": page.get("week_range", ""),
                "url": f"{pfx}/summaries/weekly/{week_id}",
            }
        )

    return {"daily": daily, "weekly": weekly}


def _list_published(
    kind: str, region: str, *, allow_draft: bool
) -> list[tuple[str, datetime]]:
    """公開可能な原稿 (doc_id, lastmod) を新しい順で返す。

    リポジトリ内ファイルと DB の候補を集め、同じ ID は DB を優先する
    （``_read_doc`` と同じ優先順位）。保持期間外は表示しない。
    """
    id_re = _DAILY_DATE_RE if kind == "daily" else _WEEKLY_ID_RE
    directory = _doc_dir(kind, region)

    entries: dict[str, tuple[str, datetime]] = {}
    if directory.is_dir():
        for path in directory.glob("*.md"):
            stem = path.stem
            if not id_re.match(stem):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=JST)
            entries[stem] = (text, mtime)
    for doc_id, body, updated_at in summary_store.list_documents(kind, region):
        if not id_re.match(doc_id):
            continue
        entries[doc_id] = (body, updated_at)

    out: list[tuple[str, datetime]] = []
    for doc_id, (text, lastmod) in entries.items():
        if not _within_retention(kind, doc_id):
            continue
        fm, _ = _split_frontmatter(text)
        meta = _parse_frontmatter(fm)
        if meta.get("generator") != "openai":
            continue
        if not _publishable(meta.get("status", "draft"), allow_draft=allow_draft):
            continue
        out.append((doc_id, lastmod))
    out.sort(key=lambda t: t[0], reverse=True)
    return out
