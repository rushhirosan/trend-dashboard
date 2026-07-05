"""Tests for scripts/daily_x_post_discord.py (module inactive in prod since 2026-07)."""

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


def test_build_payloads_jp_us_only_with_suppress_embeds(dxd):
    jp = (
        "【6/9】急上昇3（JP）\n"
        "① foo\n"
        "https://example.com/jp\n"
        "全ソース: https://trends-dashboard.fly.dev/"
    )
    us = (
        "Rising 3 (US) 6/9 · 8pm JST\n"
        "① bar\n"
        "https://example.com/us\n"
        "Dashboard: https://trends-dashboard.fly.dev/us"
    )
    payloads = dxd.build_daily_x_post_discord_payloads(jp, us)
    assert len(payloads) == 2
    assert payloads[0]["username"] == "Trend Dashboard"
    assert "embeds" not in payloads[0]
    assert payloads[0]["content"] == jp
    assert payloads[0]["flags"] == dxd._SUPPRESS_EMBEDS_FLAG
    assert payloads[1]["content"] == us
    assert payloads[1]["flags"] == dxd._SUPPRESS_EMBEDS_FLAG


def test_plain_content_rejects_over_limit(dxd):
    with pytest.raises(ValueError, match="exceeds 2000"):
        dxd._plain_content_payload("x" * 2001)


def test_notify_posts_two_messages(dxd):
    jp = "jp block"
    us = "us block"
    webhook = "https://discord.com/api/webhooks/9/abc"
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 204
    resp.text = ""
    session.post.return_value = resp

    dxd.notify_daily_x_post_discord(webhook, "2026-06-09", jp, us, session=session)

    assert session.post.call_count == 2
    bodies = [call[1]["json"] for call in session.post.call_args_list]
    assert bodies[0]["content"] == "jp block"
    assert bodies[1]["content"] == "us block"
    assert bodies[0]["flags"] == dxd._SUPPRESS_EMBEDS_FLAG


def test_notify_raises_on_http_error(dxd):
    session = MagicMock()
    ok = MagicMock(status_code=204, text="")
    bad = MagicMock(status_code=400, text="Invalid payload")
    session.post.side_effect = [ok, bad]

    with pytest.raises(RuntimeError, match="Discord HTTP 400"):
        dxd.notify_daily_x_post_discord(
            "https://discord.com/api/webhooks/1/x",
            "2026-06-09",
            "jp",
            "us",
            session=session,
        )
