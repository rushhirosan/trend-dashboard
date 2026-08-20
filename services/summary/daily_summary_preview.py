"""トップ画面用: 最新の日次サマリー Markdown からプレビューを組み立てる。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

JST = timezone(timedelta(hours=9))
# 現行は「昨日の注目」。過去原稿の「昨日/今日の一行結論」「Yesterday's takeaway」も拾う。
_ONE_LINER_HEADINGS = (
    "## 昨日の注目",
    "## 昨日の一行結論",
    "## 今日の一行結論",
    "## Bottom line",
    "## Yesterday's highlight",
    "## Yesterday's takeaway",
    "## Takeaway",
)
TEASER_MAX_CHARS = 90
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAILY_DIR = _REPO_ROOT / "docs" / "summaries" / "daily"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_BUSINESS_DAY_RE = re.compile(r'^business_day:\s*"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?', re.M)
_STATUS_RE = re.compile(r"^status:\s*(\w+)", re.M)
_GENERATOR_RE = re.compile(r"^generator:\s*(\S+)", re.M)
_SLOTS_RE = re.compile(r'snapshot_slots_included:\s*\[(.*?)\]')
_TEASER_RE = re.compile(r'^teaser:\s*"(.*)"\s*$', re.M)
_PREVIEW_LEAD_RE = re.compile(r'^preview_lead:\s*"(.*)"\s*$', re.M)
_DAILY_GENERATORS = frozenset({"openai", "mechanical"})


@dataclass(frozen=True)
class DailySummaryPreview:
    business_day: date
    delivery_day: date
    one_liner: str
    teaser: str
    snapshot_slots: tuple[str, ...]
    status: str
    source_path: Optional[Path] = None

    def headline_ja(self) -> str:
        d = self.delivery_day
        o = self.business_day
        if o == d - timedelta(days=1):
            obs_label = f"昨日（{o.month}/{o.day}）"
        else:
            obs_label = f"{o.month}/{o.day}"
        return f"日次 {d.month}/{d.day} — {obs_label}のトレンド"

    def headline_en(self) -> str:
        d = self.delivery_day
        o = self.business_day
        if o == d - timedelta(days=1):
            obs_label = f"yesterday ({o.month}/{o.day})"
        else:
            obs_label = f"{o.month}/{o.day}"
        return f"Daily {d.month}/{d.day} — trends for {obs_label}"

    def observation_meta_ja(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"観測日: {self.business_day.isoformat()}（{slots} 反映）"

    def observation_meta_en(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"Observation: {self.business_day.isoformat()} (slots {slots})"

    def subline_ja(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"{self.headline_ja()}（{slots} 反映）"

    def subline_en(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"{self.headline_en()} (slots {slots})"

    def display_teaser(self) -> str:
        return teaser_for_display(self.one_liner, self.teaser)


def _today_jst() -> date:
    return datetime.now(JST).date()


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict = {}
    bd = _BUSINESS_DAY_RE.search(block)
    if bd:
        out["business_day"] = bd.group(1)
    st = _STATUS_RE.search(block)
    if st:
        out["status"] = st.group(1)
    gen = _GENERATOR_RE.search(block)
    if gen:
        out["generator"] = gen.group(1)
    slots = _SLOTS_RE.search(block)
    if slots:
        raw = slots.group(1)
        out["snapshot_slots"] = tuple(
            s.strip().strip('"').strip("'") for s in raw.split(",") if s.strip()
        )
    teaser = _TEASER_RE.search(block)
    if teaser:
        out["teaser"] = teaser.group(1).replace('\\"', '"').strip()
    preview = _PREVIEW_LEAD_RE.search(block)
    if preview:
        out["preview_lead"] = preview.group(1).replace('\\"', '"').strip()
    return out


def first_sentence(text: str) -> str:
    """一行結論から先頭の1文を取り出す（Fake door 用フォールバック）。"""
    s = (text or "").strip()
    if not s:
        return ""
    for sep in ("。", "．"):
        idx = s.find(sep)
        if idx >= 0:
            return s[: idx + len(sep)].strip()
    if ". " in s:
        return s.split(". ", 1)[0].strip() + "."
    return s


def clamp_teaser(text: str, max_chars: int = TEASER_MAX_CHARS) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def teaser_for_display(one_liner: str, teaser: str = "") -> str:
    """トップサマリーカード用の短いリード（frontmatter teaser 優先）。"""
    explicit = (teaser or "").strip()
    if explicit:
        return clamp_teaser(explicit)
    return clamp_teaser(first_sentence(one_liner))


def extract_one_liner(markdown_body: str) -> str:
    """``## 昨日の注目``（旧: 一行結論 / takeaway）直後の本文（次の見出しまで）。"""
    idx = -1
    heading = ""
    for h in _ONE_LINER_HEADINGS:
        found = markdown_body.find(h)
        if found >= 0:
            idx, heading = found, h
            break
    if idx < 0:
        return ""
    rest = markdown_body[idx + len(heading) :]
    lines: list[str] = []
    for line in rest.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if stripped:
            lines.append(stripped)
    return " ".join(lines).strip()


def _parse_summary_file(path: Path, delivery_day: date) -> Optional[DailySummaryPreview]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _parse_summary_text(text, path.stem, delivery_day, source_path=path)


def _parse_summary_text(
    text: str,
    doc_id: str,
    delivery_day: date,
    *,
    source_path: Optional[Path] = None,
) -> Optional[DailySummaryPreview]:
    meta = _parse_frontmatter(text)
    if meta.get("generator") not in _DAILY_GENERATORS:
        return None
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            body = text[end + 4 :]
    one_liner = extract_one_liner(body)
    if not one_liner:
        one_liner = str(meta.get("preview_lead") or meta.get("teaser") or "").strip()
    if not one_liner:
        return None
    try:
        business_day = date.fromisoformat(meta.get("business_day") or doc_id)
    except ValueError:
        return None
    slots = meta.get("snapshot_slots") or ("07", "13", "19", "01")
    return DailySummaryPreview(
        business_day=business_day,
        delivery_day=delivery_day,
        one_liner=one_liner,
        teaser=str(meta.get("teaser") or "").strip(),
        snapshot_slots=tuple(slots),
        status=str(meta.get("status") or "draft"),
        source_path=source_path,
    )


def _is_publishable_status(status: str, *, allow_draft: bool) -> bool:
    st = (status or "draft").strip().lower()
    if st == "approved":
        return True
    return allow_draft and st == "draft"


def _daily_dir_for_region(region: str) -> Path:
    r = (region or "jp").strip().lower()
    return _DAILY_DIR if r == "jp" else _DAILY_DIR / r


def load_latest_daily_preview(
    daily_dir: Optional[Path] = None,
    delivery_day: Optional[date] = None,
    *,
    region: str = "jp",
    allow_draft: bool = False,
) -> Optional[DailySummaryPreview]:
    """最新の AI 生成日次からプレビューを返す（DB 優先・ファイル fallback）。

    本番想定では ``allow_draft=False``（``status: approved`` のみ）。
    """
    from services.summary import summary_store

    root = daily_dir or _daily_dir_for_region(region)
    deliver = delivery_day or _today_jst()

    # doc_id → 原稿本文。ファイルを集めたあと DB（GHA が毎朝 upsert）で上書きする。
    docs: dict[str, tuple[str, Optional[Path]]] = {}
    if root.is_dir():
        for path in root.glob("*.md"):
            if path.name == "README.md":
                continue
            try:
                docs[path.stem] = (path.read_text(encoding="utf-8"), path)
            except OSError:
                continue
    for doc_id, body, _updated_at in summary_store.list_documents(
        "daily", (region or "jp").strip().lower()
    ):
        docs[doc_id] = (body, None)

    for doc_id in sorted(docs, reverse=True):
        text, source_path = docs[doc_id]
        preview = _parse_summary_text(text, doc_id, deliver, source_path=source_path)
        if preview and _is_publishable_status(preview.status, allow_draft=allow_draft):
            return preview
    return None


def preview_for_fake_door(
    locale: str = "ja", *, region: str = "jp", allow_draft: bool = False
) -> dict:
    """テンプレート ``AI_SUMMARY_FAKE_DOOR`` 用の dict。

    ``region`` に応じて原稿ディレクトリ（jp: 直下 / us: us/）を切り替え、
    リンク用の URL 接頭辞（jp: '' / us: '/us'）も返す。
    """
    region = (region or "jp").strip().lower()
    url_prefix = "" if region == "jp" else f"/{region}"
    preview = load_latest_daily_preview(region=region, allow_draft=allow_draft)
    deliver = _today_jst()
    if preview:
        subline = preview.subline_ja() if locale == "ja" else preview.subline_en()
        return {
            "has_preview": True,
            "headline": preview.headline_ja() if locale == "ja" else preview.headline_en(),
            "subline": subline,
            "observation_meta": "",
            "teaser": preview.display_teaser(),
            "one_liner": preview.one_liner,
            "business_day": preview.business_day.isoformat(),
            "delivery_day": preview.delivery_day.isoformat(),
            "status": preview.status,
            "url_prefix": url_prefix,
        }
    fallback_headline = (
        f"日次 {deliver.month}/{deliver.day} — 準備中"
        if locale == "ja"
        else f"Daily {deliver.month}/{deliver.day} — coming soon"
    )
    return {
        "has_preview": False,
        "headline": fallback_headline,
        "subline": fallback_headline,
        "observation_meta": "",
        "teaser": "",
        "one_liner": "",
        "business_day": "",
        "delivery_day": deliver.isoformat(),
        "status": "",
        "url_prefix": url_prefix,
    }
