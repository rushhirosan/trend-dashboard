"""Tests for scripts/daily_x_post_discord.py."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "daily_x_post_discord.py"


@pytest.fixture(scope="module")
def dxd():
    spec = importlib.util.spec_from_file_location("daily_x_post_discord", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolve_discord_webhook_url_prefers_override(dxd, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    url = "https://discord.com/api/webhooks/1/token"
    assert dxd.resolve_discord_webhook_url(url) == url


def test_resolve_discord_webhook_url_from_env(dxd, monkeypatch):
    url = "https://discord.com/api/webhooks/2/token"
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", url)
    assert dxd.resolve_discord_webhook_url(None) == url


def test_resolve_discord_webhook_url_rejects_non_discord(dxd, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/hook")
    assert dxd.resolve_discord_webhook_url(None) is None


def test_build_payloads_plain_jp_us_and_reply(dxd):
    jp = (
        "【2026-06-03】今日の急上昇3つ（JP）\n"
        "① foo（検索）\n"
        "https://example.com/jp\n"
        "一覧: https://trends-dashboard.fly.dev/"
    )
    us = (
        "Today's rising 3 (US) 2026-06-03 · 8pm JST\n"
        "① bar (News)\n"
        "https://example.com/us\n"
        "一覧: https://trends-dashboard.fly.dev/us"
    )
    payloads = dxd.build_daily_x_post_discord_payloads("2026-06-03", jp, us)
    assert len(payloads) == 4
    assert payloads[0]["username"] == "Trend Dashboard"
    embed = payloads[0]["embeds"][0]
    assert embed["title"] == "X 投稿案 — 2026-06-03"
    assert "embeds" not in payloads[1]
    assert payloads[1]["content"] == jp
    assert payloads[2]["content"] == us
    assert payloads[3]["content"] == dxd.US_REPLY_SNIPPET


def test_plain_content_rejects_over_limit(dxd):
    with pytest.raises(ValueError, match="exceeds 2000"):
        dxd._plain_content_payload("x" * 2001)


def test_notify_posts_four_messages(dxd):
    jp = "jp block"
    us = "us block"
    webhook = "https://discord.com/api/webhooks/9/abc"
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 204
    resp.text = ""
    session.post.return_value = resp

    dxd.notify_daily_x_post_discord(webhook, "2026-06-03", jp, us, session=session)

    assert session.post.call_count == 4
    bodies = [call[1]["json"] for call in session.post.call_args_list]
    assert bodies[0]["embeds"][0]["title"] == "X 投稿案 — 2026-06-03"
    assert bodies[1]["content"] == "jp block"
    assert bodies[2]["content"] == "us block"
    assert bodies[3]["content"] == dxd.US_REPLY_SNIPPET


def test_notify_raises_on_http_error(dxd):
    session = MagicMock()
    ok = MagicMock(status_code=204, text="")
    bad = MagicMock(status_code=400, text="Invalid payload")
    session.post.side_effect = [ok, bad]

    with pytest.raises(RuntimeError, match="Discord HTTP 400"):
        dxd.notify_daily_x_post_discord(
            "https://discord.com/api/webhooks/1/x",
            "2026-06-03",
            "jp",
            "us",
            session=session,
        )
