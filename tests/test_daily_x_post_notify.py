"""Tests for services/daily_x_post_notify.py."""

from unittest.mock import MagicMock, patch

import pytest

from services.daily_x_post_notify import (
    run_evening_x_post_discord_notify,
    xpost_discord_dedup_key,
)


def test_xpost_discord_dedup_key():
    assert xpost_discord_dedup_key("2026-06-04") == "xpost_discord_2026-06-04"


def test_run_skips_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_EVENING_X_POST_DISCORD", raising=False)
    assert run_evening_x_post_discord_notify() is False


def test_run_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_EVENING_X_POST_DISCORD", "false")
    assert run_evening_x_post_discord_notify() is False


def test_run_skips_when_already_sent(monkeypatch):
    monkeypatch.setenv("ENABLE_EVENING_X_POST_DISCORD", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    db = MagicMock()
    db.has_slot_completed.return_value = True
    assert run_evening_x_post_discord_notify(db) is False
    db.has_slot_completed.assert_called_once()


def test_run_sends_and_marks_completed(monkeypatch):
    monkeypatch.setenv("ENABLE_EVENING_X_POST_DISCORD", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")

    db = MagicMock()
    db.has_slot_completed.return_value = False

    from datetime import date

    gx = MagicMock()
    gx.default_business_day_for_evening_x_post_jst.return_value = date(2026, 6, 4)
    gx.SNAPSHOT_SLOTS_DAYTIME = ("07", "13", "19")
    gx.load_snapshots_daytime_slots.return_value = {"07": {}, "13": {}, "19": {}}
    gx.build_x_post_blocks_for_discord_copy.return_value = ("jp copy", "us copy")

    dxd = MagicMock()
    dxd.resolve_discord_webhook_url.return_value = "https://discord.com/api/webhooks/1/x"

    with patch(
        "services.daily_x_post_notify._import_x_post_modules",
        return_value=(gx, dxd),
    ):
        assert run_evening_x_post_discord_notify(db) is True

    dxd.notify_daily_x_post_discord.assert_called_once_with(
        "https://discord.com/api/webhooks/1/x",
        "2026-06-04",
        "jp copy",
        "us copy",
    )
    db.mark_slot_completed.assert_called_once_with("xpost_discord_2026-06-04")
