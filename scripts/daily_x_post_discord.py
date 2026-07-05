"""
Discord Webhook へ日次 X 投稿案（JP / US）を送る。

**運用停止（2026-07）— 本番・GHA・スケジューラからは呼ばれない。**
手動で ``generate_daily_x_post_series.py --discord`` を実行したときのみ利用。

Webhook URL はスケジューラ通知と同じ ``DISCORD_WEBHOOK_URL``（``utils/alert_service`` と共通）。

JP / US 各1通のプレーン ``content`` のみ（Embed・読む用の長文・US 返信は送らない）。
リンクプレビューは ``SUPPRESS_EMBEDS`` で抑制する。
"""

from __future__ import annotations

import os
from typing import Any

import requests

_DISCORD_CONTENT_MAX = 2000
_WEBHOOK_USERNAME = "Trend Dashboard"
# Discord MessageFlags: SUPPRESS_EMBEDS — 記事 URL のプレビューカード防止
_SUPPRESS_EMBEDS_FLAG = 1 << 2


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
    return {
        **_webhook_base(),
        "content": body,
        "flags": _SUPPRESS_EMBEDS_FLAG,
    }


def build_daily_x_post_discord_payloads(jp: str, us: str) -> list[dict[str, Any]]:
    """Webhook POST 用 JSON のリスト（JP → US の2通）。"""
    return [
        _plain_content_payload(jp),
        _plain_content_payload(us),
    ]


def build_daily_x_post_discord_payload(date_str: str, jp: str, us: str) -> dict[str, Any]:
    """後方互換: JP 文案ペイロードのみ返す。"""
    del date_str
    return _plain_content_payload(jp)


def notify_daily_x_post_discord(
    webhook_url: str,
    date_str: str,
    jp: str,
    us: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 30.0,
) -> None:
    """Discord Webhook に日次 X 投稿案を POST（JP / US の2メッセージ）。HTTP エラー時は RuntimeError。"""
    del date_str
    http = session or requests
    for payload in build_daily_x_post_discord_payloads(jp, us):
        resp = http.post(webhook_url, json=payload, timeout=timeout)
        if resp.status_code >= 400:
            body = (resp.text or "")[:500]
            raise RuntimeError(f"Discord HTTP {resp.status_code}: {body}")
