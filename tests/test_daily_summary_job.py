"""Fly 日次サマリー生成ジョブ（スナップショット確認 → DB → メール順）。"""

from unittest.mock import patch

from services.summary.daily_summary_job import (
    DailySummaryJobResult,
    default_business_day_jst,
    run_daily_summary_job,
)


def test_default_business_day_is_jst_yesterday():
    from datetime import datetime, timezone, timedelta

    jst = timezone(timedelta(hours=9))
    now = datetime(2026, 11, 26, 8, 30, tzinfo=jst)
    assert default_business_day_jst(now=now).isoformat() == "2026-11-25"


@patch("services.summary.daily_summary_job.already_published", return_value=True)
def test_skips_when_already_published(_already):
    result = run_daily_summary_job(business_day="2026-11-25")
    assert result.skipped is True
    assert result.reason == "already_published"
    assert result.ok is True


@patch("services.summary.daily_summary_job.already_published", return_value=False)
@patch(
    "services.summary.daily_summary_job.snapshot_slots_present",
    return_value=(False, {"07", "13"}),
)
def test_aborts_when_snapshots_incomplete(_slots, _already):
    result = run_daily_summary_job(business_day="2026-11-25", send_mail=False)
    assert result.skipped is False
    assert result.ok is False
    assert any("snapshots_incomplete" in e for e in result.errors)


@patch("services.summary.daily_summary_job.send_emails", return_value=(True, []))
@patch("services.summary.daily_summary_job.attach_and_publish_thumbs")
@patch(
    "services.summary.daily_summary_job.publish_markdown_to_db",
    return_value=["jp", "us"],
)
@patch(
    "services.summary.daily_summary_job.generate_region_markdown",
    side_effect=lambda bd, region, force=True: (True, "ok"),
)
@patch(
    "services.summary.daily_summary_job.snapshot_slots_present",
    return_value=(True, {"07", "13", "19", "01"}),
)
@patch("services.summary.daily_summary_job.already_published", return_value=False)
def test_happy_path_db_then_email(
    _already, _slots, _gen, _pub, _thumbs, send_mail
):
    result = run_daily_summary_job(business_day="2026-11-25")
    assert result.ok is True
    assert result.published == ["jp", "us"]
    assert result.email_ok is True
    send_mail.assert_called_once_with("2026-11-25")
    _thumbs.assert_called_once_with("2026-11-25")


@patch("services.summary.daily_summary_job.send_emails")
@patch("services.summary.daily_summary_job.attach_and_publish_thumbs")
@patch(
    "services.summary.daily_summary_job.publish_markdown_to_db",
    return_value=["jp"],
)
@patch(
    "services.summary.daily_summary_job.generate_region_markdown",
    side_effect=lambda bd, region, force=True: (region == "jp", "ok" if region == "jp" else "fail"),
)
@patch(
    "services.summary.daily_summary_job.snapshot_slots_present",
    return_value=(True, {"07", "13", "19", "01"}),
)
@patch("services.summary.daily_summary_job.already_published", return_value=False)
def test_skips_email_when_not_both_regions(
    _already, _slots, _gen, _pub, _thumbs, send_mail
):
    result = run_daily_summary_job(business_day="2026-11-25")
    assert result.ok is False
    assert "email_skipped: not_both_regions_published" in result.errors
    send_mail.assert_not_called()


def test_result_ok_property():
    assert DailySummaryJobResult(business_day="x", skipped=True).ok is True
    assert (
        DailySummaryJobResult(
            business_day="x", published=["jp", "us"]
        ).ok
        is True
    )
    assert DailySummaryJobResult(business_day="x", published=["jp"]).ok is False
