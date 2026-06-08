"""
Discord Webhook へ日次 X 投稿案（JP / US）を送る。

``generate_daily_x_post_series.py --discord`` から利用。
Webhook URL はスケジューラ通知と同じ ``DISCORD_WEBHOOK_URL``（``utils/alert_service`` と共通）。

JP / US 文案は Embed field ではなくプレーン ``content`` メッセージで送る。
iPhone でも長押し「テキストをコピー」→ X 貼り付けがしやすい（Embed field は iOS で選択不可）。
"""

from __future__ import annotations

import os
from typing import Any

import requests

US_REPLY_SNIPPET = (
    "Dashboard refreshes on a JST schedule (1/7/13/19 JST). "
    "Same post time as our JP tweet (8pm JST ≈ US morning)."
)

DATA_STATUS_URL = "https://trends-dashboard.fly.dev/data-status"
_EMBED_COLOR = 0x5865F2  # Discord blurple — コピー用通知と区別しやすい
_DISCORD_CONTENT_MAX = 2000
_WEBHOOK_USERNAME = "Trend Dashboard"


def resolve_discord_webhook_url(override: str | None = None) -> str | None:
    """CLI 引数 → DISCORD_WEBHOOK_URL の順で Webhook URL を返す。無効なら None。"""
    url = (override or os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    if url and "discord" in url.lower():
        return url
    return None


def _webhook_base() -> dict[str, Any]:
    return {"username": _WEBHOOK_USERNAME}


def _plain_content_payload(text: str) -> dict[str, Any]:
    body = (text or "").strip()
    if not body:
        raise ValueError("Discord content must not be empty")
    if len(body) > _DISCORD_CONTENT_MAX:
        raise ValueError(
            f"Discord content exceeds {_DISCORD_CONTENT_MAX} chars ({len(body)})"
        )
    return {**_webhook_base(), "content": body}


def build_daily_x_post_discord_header_payload(date_str: str) -> dict[str, Any]:
    """説明用 Embed のみ（コピー対象の文案は含めない）。"""
    return {
        **_webhook_base(),
        "embeds": [
            {
                "title": f"X 投稿案 — {date_str}",
                "description": (
                    "下の **JP → US → US 返信** を順に長押し → **テキストをコピー** で X に貼り付け。"
                    " 記事 URL は行ごと含まれています。"
                ),
                "color": _EMBED_COLOR,
                "footer": {"text": f"鮮度確認: {DATA_STATUS_URL}"},
            }
        ],
    }


def build_daily_x_post_discord_payloads(
    date_str: str, jp: str, us: str
) -> list[dict[str, Any]]:
    """Webhook POST 用 JSON のリスト（ヘッダー Embed + JP/US/返信のプレーン文）。"""
    return [
        build_daily_x_post_discord_header_payload(date_str),
        _plain_content_payload(jp),
        _plain_content_payload(us),
        _plain_content_payload(US_REPLY_SNIPPET),
    ]


def build_daily_x_post_discord_payload(date_str: str, jp: str, us: str) -> dict[str, Any]:
    """後方互換: 先頭ペイロード（ヘッダー Embed）のみ返す。"""
    return build_daily_x_post_discord_header_payload(date_str)


def notify_daily_x_post_discord(
    webhook_url: str,
    date_str: str,
    jp: str,
    us: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> None:
    """Discord Webhook に日次 X 投稿案を POST（複数メッセージ）。HTTP エラー時は RuntimeError。"""
    http = session or requests
    for payload in build_daily_x_post_discord_payloads(date_str, jp, us):
        resp = http.post(webhook_url, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            body = (resp.text or "")[:500]
            raise RuntimeError(f"Discord HTTP {resp.status_code}: {body}")
