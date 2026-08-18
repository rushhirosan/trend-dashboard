"""Paid summary email tests (no live DB / Resend)."""

from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from services.summary.summary_paid_email import (
    SubscribersApiUnavailable,
    fetch_active_subscribers_from_site,
    send_summary_paid,
)


@patch("services.summary.summary_paid_email.load_summary_email_bodies")
def test_send_summary_paid_dry_run_injected(mock_load):
    mock_load.return_value = (Path("x.md"), "body", "<p>body</p>")
    results = send_summary_paid(
        kind="daily",
        doc_id="2026-08-18",
        dry_run=True,
        subscribers=[
            {"email": "jp@example.com", "region_plan": "jp"},
            {"email": "both@example.com", "region_plan": "both"},
        ],
    )
    pairs = {(r.email, r.region) for r in results if r.ok}
    assert pairs == {
        ("jp@example.com", "jp"),
        ("both@example.com", "jp"),
        ("both@example.com", "us"),
    }
    assert all("(dogfood)" not in (r.error or "") for r in results)


@patch("services.summary.summary_paid_email.urllib.request.urlopen")
def test_fetch_subscribers_404_is_unavailable(mock_urlopen):
    mock_urlopen.side_effect = HTTPError(
        url="https://example.com/api",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )
    try:
        fetch_active_subscribers_from_site(
            base_url="https://example.com",
            token="secret",
        )
        assert False, "expected SubscribersApiUnavailable"
    except SubscribersApiUnavailable:
        pass
