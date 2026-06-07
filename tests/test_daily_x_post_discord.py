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


def test_build_payload_includes_jp_us_code_blocks(dxd):
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
    payload = dxd.build_daily_x_post_discord_payload("2026-06-03", jp, us)
    assert payload["username"] == "Trend Dashboard"
    embed = payload["embeds"][0]
    assert embed["title"] == "X 投稿案 — 2026-06-03"
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    jp_block = fields["JP — 今日の急上昇3つ"]
    us_block = fields["US — Today's rising 3"]
    assert jp_block.startswith("```") and jp_block.endswith("```")
    assert "① foo（検索）\nhttps://example.com/jp" in jp_block
    assert "一覧: https://trends-dashboard.fly.dev/" in jp_block
    assert us_block.startswith("```") and us_block.endswith("```")
    assert "① bar (News)\nhttps://example.com/us" in us_block
    assert dxd.US_REPLY_SNIPPET in fields["US 返信（任意・英語）"]


def test_plain_x_post_to_discord_markdown_leaves_header_lines(dxd):
    jp = "【2026-06-03】今日の急上昇3つ（JP）\n① only title（検索）"
    out = dxd.plain_x_post_to_discord_markdown(jp)
    assert out == jp


def test_discord_link_label_escapes_brackets(dxd):
    assert dxd._discord_link_label("a[b]c") == "a［b］c"


def test_code_block_escapes_inner_backticks(dxd):
    text = "line with ``` inside"
    wrapped = dxd._code_block(text)
    assert wrapped.startswith("````")
    assert text in wrapped


def test_notify_posts_json(dxd, monkeypatch):
    jp = "jp block"
    us = "us block"
    webhook = "https://discord.com/api/webhooks/9/abc"
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 204
    resp.text = ""
    session.post.return_value = resp

    dxd.notify_daily_x_post_discord(webhook, "2026-06-03", jp, us, session=session)

    session.post.assert_called_once()
    call_kw = session.post.call_args
    assert call_kw[0][0] == webhook
    body = call_kw[1]["json"]
    assert "jp block" in body["embeds"][0]["fields"][0]["value"]
    assert body["embeds"][0]["fields"][0]["value"].startswith("```")


def test_notify_raises_on_http_error(dxd):
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "Invalid payload"
    session.post.return_value = resp

    with pytest.raises(RuntimeError, match="Discord HTTP 400"):
        dxd.notify_daily_x_post_discord(
            "https://discord.com/api/webhooks/1/x",
            "2026-06-03",
            "jp",
            "us",
            session=session,
        )
