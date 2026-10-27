"""日次サムネを、話題が同じなら前日の画像から、変わったら画像 API から付ける。

GitHub Actions の日次ジョブが Markdown を書いたあとに呼ぶ。ファイルが既にある日は
触らない。画像 API が無い・失敗した日は画像なしのままにして、原稿の公開は止めない。
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DAILY = _REPO_ROOT / "docs" / "summaries" / "daily"
THUMB_ROOT = _REPO_ROOT / "static" / "images" / "summaries" / "daily"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_THUMB_SUFFIXES = (".jpg", ".jpeg", ".png")
_RANK_JP = re.compile(r"（[^）]*）\s*。?\s*$")
_RANK_EN = re.compile(r"\s*\([^)]*\)\s*\.?\s*$")
_LEAD_LINE = re.compile(r'^(preview_lead|teaser):\s*"(.*)"\s*$', re.M)

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"

GenerateFn = Callable[[str], Optional[bytes]]


def topic_key(lead: str) -> str:
    """順位の括弧を除いたリード。同じ話題の日は同じキーになる。"""
    text = (lead or "").strip()
    text = _RANK_JP.sub("", text).strip()
    text = _RANK_EN.sub("", text).strip()
    return text.rstrip("。").strip()


def read_preview_lead(markdown: str) -> str:
    """frontmatter の preview_lead（無ければ teaser）を返す。"""
    if not markdown.startswith("---"):
        return ""
    end = markdown.find("\n---", 3)
    if end < 0:
        return ""
    found = {key: _unescape_lead(value) for key, value in _LEAD_LINE.findall(markdown[:end])}
    return found.get("preview_lead") or found.get("teaser") or ""


def _unescape_lead(value: str) -> str:
    """generate 側の \\\\ と \\" だけを戻す。"""
    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value) and value[i + 1] in ("\\", '"'):
            out.append(value[i + 1])
            i += 2
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def find_thumb(thumb_dir: Path, day: str) -> Optional[Path]:
    for suffix in _THUMB_SUFFIXES:
        path = thumb_dir / f"{day}{suffix}"
        if path.is_file():
            return path
    return None


def earlier_days(docs_dir: Path, day: str) -> list[str]:
    days = []
    if not docs_dir.is_dir():
        return days
    for path in docs_dir.glob("*.md"):
        if _DATE_RE.match(path.stem) and path.stem < day:
            days.append(path.stem)
    return sorted(days, reverse=True)


def reuse_source(docs_dir: Path, thumb_dir: Path, day: str, lead: str) -> Optional[Path]:
    """同じ話題が続いている間、いちばん新しい既存画像を返す。話題が変わったら None。"""
    key = topic_key(lead)
    if not key:
        return None
    for prev in earlier_days(docs_dir, day):
        prev_md = docs_dir / f"{prev}.md"
        try:
            prev_lead = read_preview_lead(prev_md.read_text(encoding="utf-8"))
        except OSError:
            return None
        if topic_key(prev_lead) != key:
            return None
        thumb = find_thumb(thumb_dir, prev)
        if thumb:
            return thumb
    return None


def attach_one(
    docs_dir: Path,
    thumb_dir: Path,
    day: str,
    *,
    generate: GenerateFn,
) -> str:
    """その日のサムネを付ける。戻り値は skip / reuse / generated / missing。"""
    if not _DATE_RE.match(day or ""):
        return "missing"
    md_path = docs_dir / f"{day}.md"
    if not md_path.is_file():
        return "missing"
    if find_thumb(thumb_dir, day):
        return "skip"
    try:
        lead = read_preview_lead(md_path.read_text(encoding="utf-8"))
    except OSError:
        return "missing"
    source = reuse_source(docs_dir, thumb_dir, day, lead)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    if source is not None:
        dest = thumb_dir / f"{day}{source.suffix.lower()}"
        dest.write_bytes(source.read_bytes())
        return "reuse"
    if not topic_key(lead):
        return "missing"
    image = generate(topic_key(lead))
    if not image:
        return "missing"
    (thumb_dir / f"{day}.png").write_bytes(image)
    return "generated"


def openai_generate(topic: str) -> Optional[bytes]:
    """dall-e-2 で 256px の PNG を作る。鍵が無い・失敗時は None。"""
    key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY") or "").strip()
    if not key:
        print("OPENAI_API_KEY が無いので、新しいサムネは作りません。")
        return None
    model = (os.getenv("OPENAI_THUMB_MODEL") or "dall-e-2").strip()
    prompt = (
        "Square flat vector icon, one bold simple object centered, thick shapes readable at 64 pixels, "
        "solid flat background. Suggest this topic without drawing any words: "
        f"{topic[:180]}. "
        "No text, no letters, no numbers, no logos, no watermark, no photorealism, no people, no violence."
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "256x256",
            "response_format": "b64_json",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_IMAGES_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        encoded = body["data"][0]["b64_json"]
        return base64.b64decode(encoded)
    except (urllib.error.URLError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "read", None)
        extra = ""
        if callable(detail):
            try:
                extra = detail().decode("utf-8", errors="replace")[:200]
            except Exception:
                extra = ""
        print(f"サムネ生成に失敗しました: {exc} {extra}".rstrip())
        return None


def docs_dir_for(region: str) -> Path:
    if region == "us":
        return DOCS_DAILY / "us"
    return DOCS_DAILY


def thumb_dir_for(region: str) -> Path:
    return THUMB_ROOT / ("us" if region == "us" else "jp")


def attach_missing(
    *,
    only_date: str = "",
    regions: tuple[str, ...] = ("jp", "us"),
    generate: Optional[GenerateFn] = None,
) -> int:
    """画像が無い日次だけ処理する。失敗しても 0 を返し、原稿コミットは止めない。"""
    generate = generate or openai_generate
    for region in regions:
        docs_dir = docs_dir_for(region)
        thumb_dir = thumb_dir_for(region)
        if only_date:
            days = [only_date]
        elif docs_dir.is_dir():
            days = sorted(p.stem for p in docs_dir.glob("*.md") if _DATE_RE.match(p.stem))
        else:
            days = []
        for day in days:
            try:
                result = attach_one(docs_dir, thumb_dir, day, generate=generate)
            except Exception as exc:
                print(f"{region}/{day}: missing ({exc})")
                continue
            print(f"{region}/{day}: {result}")
    return 0
