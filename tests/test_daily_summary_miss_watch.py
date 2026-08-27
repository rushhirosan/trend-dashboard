"""Fly 08:15 JST 日次サマリー欠走チェック（生成・メールはしない）。"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytz

from services.scheduler.scheduler_manager import TrendsScheduler

JST = pytz.timezone("Asia/Tokyo")
_NOW = JST.localize(datetime(2026, 8, 27, 8, 15, 0))
_DOC = "2026-08-26"


def _make_scheduler():
    app = MagicMock()
    app.config = {"TREND_MANAGERS": {}}
    sched = TrendsScheduler(app)
    sent = []

    def fake_send(level, title, message, details=None):
        sent.append((level, title, message, details))
        return True

    sched._send_alert = fake_send
    return sched, sent


def test_daily_summary_business_day_is_jst_yesterday():
    sched, _sent = _make_scheduler()
    assert sched._daily_summary_business_day_jst(_NOW) == _DOC


@patch("services.summary.summary_store.has_document", return_value=True)
def test_check_skips_alert_when_jp_and_us_exist(_has):
    sched, sent = _make_scheduler()
    sched._check_daily_summary_published(now=_NOW)
    assert sent == []


@patch(
    "services.summary.summary_store.has_document",
    side_effect=lambda kind, region, doc_id: region != "us",
)
def test_check_alerts_when_one_region_missing(_has):
    sched, sent = _make_scheduler()
    sched._check_daily_summary_published(now=_NOW)
    assert len(sent) == 1
    level, title, message, details = sent[0]
    assert level == "warning"
    assert "未着" in title
    assert _DOC in message
    assert details["missing"] == "us"
    assert "Run workflow" in details["対応"]


@patch("services.summary.summary_store.has_document", return_value=None)
def test_check_does_not_treat_db_error_as_miss(_has):
    sched, sent = _make_scheduler()
    sched._check_daily_summary_published(now=_NOW)
    assert sent == []
