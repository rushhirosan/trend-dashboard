"""
Discord Webhook へ日次 X 投稿案（JP / US）を送る。

``generate_daily_x_post_series.py --discord`` から利用。
Webhook URL はスケジューラ通知と同じ ``DISCORD_WEBHOOK_URL``（``utils/alert_service`` と共通）。
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

_URL_LINE = re.compile(r"^https?://\S+$", re.I)
_LIST_LINE = re.compile(r"^一覧:\s*(https?://\S+)\s*$")

US_REPLY_SNIPPET = (
    "Dashboard refreshes on a JST schedule (1/7/13/19 JST). "
    "Same post time as our JP tweet (8pm JST ≈ US morning)."
)

DATA_STATUS_URL = "https://trends-dashboard.fly.dev/data-status"
_EMBED_COLOR = 0x5865F2  # Discord blurple — コピー用通知と区別しやすい


def resolve_discord_webhook_url(override: str | None = None) -> str | None:
    """CLI 引数 → DISCORD_WEBHOOK_URL の順で Webhook URL を返す。無効なら None。"""
    url = (override or os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if url and "discord" in url.lower():
        return url
    return None


def _code_block(text: str) -> str:
    """Discord embed field 用。本文に ``` が含まれても壊れにくいようフェンスを調整。"""
    body = (text or "").strip()
    fence = "```"
    while fence in body:
        fence += "`"
    return f"{fence}\n{body}\n{fence}"


def _discord_link_label(text: str) -> str:
    """Discord の [label](url) が壊れないよう角括弧を全角に。"""
    return text.replace("[", "［").replace("]", "］")


def _discord_link(label: str, url: str) -> str:
    return f"[{_discord_link_label(label)}](<{url}>)"


def plain_x_post_to_discord_markdown(text: str) -> str:
    """
    X 投稿案（見出し + 次行 URL）を Discord embed 用 Markdown に変換する。
    コードブロック内では URL がリンク化されないため、embed field ではこちらを使う。
    """
    lines = (text or "").strip().split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if next_line and _URL_LINE.match(next_line):
            out.append(_discord_link(line, next_line))
            i += 2
            continue
        list_match = _LIST_LINE.match(line.strip())
        if list_match:
            out.append(_discord_link("一覧", list_match.group(1)))
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def build_daily_x_post_discord_payload(date_str: str, jp: str, us: str) -> dict[str, Any]:
    """Webhook POST 用 JSON（1 embed・JP/US はクリック可能な Markdown リンク）。"""
    return {
        "username": "Trend Dashboard",
        "embeds": [
            {
                "title": f"X 投稿案 — {date_str}",
                "description": (
                    "各項目はリンク付き（タップで記事へ）。"
                    " X 投稿用のプレーン文案は `generate_daily_x_post_series.py --write` か GitHub Actions。"
                    " JP を先、US を後。任意で US 返信文を返信ツイートに。"
                ),
                "color": _EMBED_COLOR,
                "fields": [
                    {
                        "name": "JP — 今日の急上昇3つ",
                        "value": plain_x_post_to_discord_markdown(jp),
                        "inline": False,
                    },
                    {
                        "name": "US — Today's rising 3",
                        "value": plain_x_post_to_discord_markdown(us),
                        "inline": False,
                    },
                    {
                        "name": "US 返信（任意・英語）",
                        "value": _code_block(US_REPLY_SNIPPET),
                        "inline": False,
                    },
                ],
                "footer": {"text": f"鮮度確認: {DATA_STATUS_URL}"},
            }
        ],
    }


def notify_daily_x_post_discord(
    webhook_url: str,
    date_str: str,
    jp: str,
    us: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> None:
    """Discord Webhook に日次 X 投稿案を POST。HTTP エラー時は RuntimeError。"""
    payload = build_daily_x_post_discord_payload(date_str, jp, us)
    http = session or requests
    resp = http.post(webhook_url, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        body = (resp.text or "")[:500]
        raise RuntimeError(f"Discord HTTP {resp.status_code}: {body}")
