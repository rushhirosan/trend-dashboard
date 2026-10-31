"""日次サムネを、話題が同じなら前日の画像から、変わったら画像 API から付ける。

GitHub Actions の日次ジョブが Markdown を書いたあとに呼ぶ。ファイルが既にある日は
触らない。画像 API が無い・失敗した日は幾何アイコンへフォールバックし、一覧の穴を避ける。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import urllib.error
import urllib.request
import zlib
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


# 画像 API が弾きやすい語。失敗時のフォールバック題材を決めるときに使う。
_SENSITIVE_TOPIC = re.compile(
    r"戦闘機|ミサイル|爆弾|戦争|軍事|weapon|fighter|missile|bomb|war\b|military",
    re.I,
)


def safe_fallback_topic(topic: str) -> str:
    """本番トピックが安全フィルタで落ちやすいときの代替題材。"""
    if _SENSITIVE_TOPIC.search(topic or ""):
        return "international diplomatic summit, three simple flags side by side"
    return "simple abstract news spotlight icon, bold geometric shape"


def openai_generate(topic: str) -> Optional[bytes]:
    """画像 API でサムネを作る。失敗・鍵なし・残高切れなら幾何アイコンへ落とす。

    既定モデルは gpt-image-1-mini（安くて一覧サムネ向き。OPENAI_THUMB_MODEL で変更可）。
    戦闘機など安全フィルタに弾かれやすい題材は、穏やかな代替題材で一度だけ再試行する。
    """
    key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY") or "").strip()
    if key:
        image, err = _openai_generate_once(key, topic)
        if image:
            return image
        # 残高切れなどはプロンプトを変えても同じなので、代替題材は試さない
        if err and "insufficient_quota" not in err and "credit" not in err.lower():
            fallback = safe_fallback_topic(topic)
            if fallback != topic:
                print(f"代替題材で再試行します: {fallback}")
                image, _ = _openai_generate_once(key, fallback)
                if image:
                    return image
    else:
        print("OPENAI_API_KEY が無いので、幾何アイコンにフォールバックします。")
    print(f"幾何アイコンにフォールバックします: {topic_key(topic)[:60]}")
    return procedural_generate(topic)


def _openai_payload(model: str, prompt: str) -> dict:
    """モデル差分（dall-e-2 の response_format / 256px と gpt-image-1）を吸収する。"""
    if model.startswith("dall-e"):
        return {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "256x256",
            "response_format": "b64_json",
        }
    # gpt-image-1 系は response_format を受け付けず、既定で b64_json を返す
    size = (os.getenv("OPENAI_THUMB_SIZE") or "1024x1024").strip()
    return {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }


def _openai_generate_once(key: str, topic: str) -> tuple[Optional[bytes], str]:
    """成功時は (bytes, "")、失敗時は (None, エラー抜粋)。"""
    model = (os.getenv("OPENAI_THUMB_MODEL") or "gpt-image-1-mini").strip()
    prompt = (
        "Square flat vector icon, one bold simple object centered, thick shapes readable at 64 pixels, "
        "solid flat background. Suggest this topic without drawing any words: "
        f"{topic[:180]}. "
        "No text, no letters, no numbers, no logos, no watermark, no photorealism, no people, no violence."
    )
    payload = json.dumps(_openai_payload(model, prompt)).encode("utf-8")
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
        return base64.b64decode(encoded), ""
    except (urllib.error.URLError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "read", None)
        extra = ""
        if callable(detail):
            try:
                extra = detail().decode("utf-8", errors="replace")[:200]
            except Exception:
                extra = ""
        print(f"サムネ生成に失敗しました: {exc} {extra}".rstrip())
        return None, f"{exc} {extra}"


def _png_rgb(width: int, height: int, rgb: bytearray) -> bytes:
    """非圧縮相当の RGB PNG を stdlib だけで書く（依存追加を避ける）。"""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    rows = bytearray()
    stride = width * 3
    for y in range(height):
        rows.append(0)
        rows.extend(rgb[y * stride : (y + 1) * stride])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def _blend(bg: tuple[int, int, int], fg: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(b + (f - b) * t) for b, f in zip(bg, fg))


def _motif_for(topic: str) -> str:
    text = topic or ""
    if re.search(r"漏洩|流出|leak|breach|メール|email|ドメイン|domain|個人情報|privacy", text, re.I):
        return "shield"
    if re.search(r"JUMANJI|trailer|game|ゲーム|映画", text, re.I):
        return "board"
    if re.search(r"Vegemite|jar|食品|food", text, re.I):
        return "jar"
    if re.search(r"台風|storm|weather|猛烈", text, re.I):
        return "spiral"
    return "spotlight"


def procedural_generate(topic: str, size: int = 256) -> bytes:
    """話題から色とモチーフを決めたフラットな PNG。API が使えない日の穴埋め。"""
    digest = hashlib.sha256((topic or "trend").encode("utf-8")).digest()
    # 彩度高めの背景色（紫系の定番寄せは避ける）
    hue_buckets = [
        (30, 90, 140),
        (20, 120, 100),
        (180, 90, 70),
        (50, 110, 160),
        (140, 70, 90),
        (70, 100, 60),
    ]
    bg = hue_buckets[digest[0] % len(hue_buckets)]
    fg = (245, 245, 240)
    accent = _blend(bg, (255, 220, 120), 0.55)
    rgb = bytearray(size * size * 3)
    for i in range(0, len(rgb), 3):
        rgb[i : i + 3] = bytes(bg)

    def set_px(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 3
            rgb[i : i + 3] = bytes(color)

    def fill_circle(cx: int, cy: int, r: int, color: tuple[int, int, int]) -> None:
        r2 = r * r
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r2:
                    set_px(x, y, color)

    def fill_rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(y0, y1):
            for x in range(x0, x1):
                set_px(x, y, color)

    cx = cy = size // 2
    motif = _motif_for(topic)
    if motif == "shield":
        fill_circle(cx, cy + 8, 70, fg)
        fill_rect(cx - 18, cy - 40, cx + 18, cy + 10, accent)
        fill_circle(cx, cy - 40, 18, accent)
        fill_rect(cx - 8, cy - 10, cx + 8, cy + 36, bg)
    elif motif == "board":
        fill_rect(cx - 72, cy - 72, cx + 72, cy + 72, fg)
        fill_rect(cx - 60, cy - 60, cx + 60, cy + 60, accent)
        for i in range(-1, 2):
            fill_rect(cx + i * 30 - 4, cy - 60, cx + i * 30 + 4, cy + 60, fg)
            fill_rect(cx - 60, cy + i * 30 - 4, cx + 60, cy + i * 30 + 4, fg)
        fill_circle(cx, cy, 16, bg)
    elif motif == "jar":
        fill_rect(cx - 40, cy - 20, cx + 40, cy + 70, fg)
        fill_rect(cx - 48, cy - 40, cx + 48, cy - 12, accent)
        fill_rect(cx - 28, cy - 55, cx + 28, cy - 40, fg)
    elif motif == "spiral":
        fill_circle(cx, cy, 78, fg)
        fill_circle(cx + 10, cy - 6, 52, accent)
        fill_circle(cx + 18, cy - 10, 28, bg)
    else:
        fill_circle(cx, cy + 10, 78, accent)
        fill_circle(cx, cy - 20, 36, fg)
        fill_rect(cx - 10, cy + 10, cx + 10, cy + 70, fg)

    return _png_rgb(size, size, rgb)


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
