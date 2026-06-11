"""トップ画面用: 最新の日次サマリー Markdown からプレビューを組み立てる。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

JST = timezone(timedelta(hours=9))
_ONE_LINER_HEADING = "## 今日の一行結論"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DAILY_DIR = _REPO_ROOT / "docs" / "summaries" / "daily"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_BUSINESS_DAY_RE = re.compile(r'^business_day:\s*"?([0-9]{4}-[0-9]{2}-[0-9]{2})"?', re.M)
_STATUS_RE = re.compile(r"^status:\s*(\w+)", re.M)
_GENERATOR_RE = re.compile(r"^generator:\s*(\S+)", re.M)
_SLOTS_RE = re.compile(r'snapshot_slots_included:\s*\[(.*?)\]')


@dataclass(frozen=True)
class DailySummaryPreview:
    business_day: date
    delivery_day: date
    one_liner: str
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
        return f"{d.month}/{d.day} 朝刊 — {obs_label}のトレンド"

    def headline_en(self) -> str:
        d = self.delivery_day
        o = self.business_day
        if o == d - timedelta(days=1):
            obs_label = f"yesterday ({o.month}/{o.day})"
        else:
            obs_label = f"{o.month}/{o.day}"
        return f"{d.month}/{d.day} briefing — trends for {obs_label}"

    def observation_meta_ja(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"観測日: {self.business_day.isoformat()}（{slots} 反映）"

    def observation_meta_en(self) -> str:
        slots = "/".join(self.snapshot_slots) if self.snapshot_slots else "07/13/19/01"
        return f"Observation: {self.business_day.isoformat()} (slots {slots})"


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
    return out


def extract_one_liner(markdown_body: str) -> str:
    """``## 今日の一行結論`` 直後の本文（次の見出しまで）。"""
    idx = markdown_body.find(_ONE_LINER_HEADING)
    if idx < 0:
        return ""
    rest = markdown_body[idx + len(_ONE_LINER_HEADING) :]
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
    meta = _parse_frontmatter(text)
    if meta.get("generator") != "openai":
        return None
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end >= 0:
            body = text[end + 4 :]
    one_liner = extract_one_liner(body)
    if not one_liner:
        return None
    try:
        business_day = date.fromisoformat(meta.get("business_day") or path.stem)
    except ValueError:
        return None
    slots = meta.get("snapshot_slots") or ("07", "13", "19", "01")
    return DailySummaryPreview(
        business_day=business_day,
        delivery_day=delivery_day,
        one_liner=one_liner,
        snapshot_slots=tuple(slots),
        status=str(meta.get("status") or "draft"),
        source_path=path,
    )


def load_latest_daily_preview(
    daily_dir: Optional[Path] = None,
    delivery_day: Optional[date] = None,
) -> Optional[DailySummaryPreview]:
    """``docs/summaries/daily/`` の最新 AI 生成日次から一行結論を返す。"""
    root = daily_dir or _DAILY_DIR
    if not root.is_dir():
        return None
    deliver = delivery_day or _today_jst()
    candidates = sorted(
        (p for p in root.glob("*.md") if p.name != "README.md"),
        key=lambda p: p.stem,
        reverse=True,
    )
    for path in candidates:
        preview = _parse_summary_file(path, deliver)
        if preview:
            return preview
    return None


def preview_for_fake_door(locale: str = "ja") -> dict:
    """テンプレート ``AI_SUMMARY_FAKE_DOOR`` 用の dict。"""
    preview = load_latest_daily_preview()
    deliver = _today_jst()
    if preview:
        return {
            "has_preview": True,
            "headline": preview.headline_ja() if locale == "ja" else preview.headline_en(),
            "observation_meta": (
                preview.observation_meta_ja() if locale == "ja" else preview.observation_meta_en()
            ),
            "one_liner": preview.one_liner,
            "business_day": preview.business_day.isoformat(),
            "delivery_day": preview.delivery_day.isoformat(),
            "status": preview.status,
        }
    fallback_headline = (
        f"{deliver.month}/{deliver.day} 朝刊 — 準備中"
        if locale == "ja"
        else f"{deliver.month}/{deliver.day} briefing — coming soon"
    )
    return {
        "has_preview": False,
        "headline": fallback_headline,
        "observation_meta": "",
        "one_liner": "",
        "business_day": "",
        "delivery_day": deliver.isoformat(),
        "status": "",
    }
