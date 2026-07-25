"""Tests for summary dogfood email helpers."""

from datetime import date
from pathlib import Path

from services.summary.summary_dogfood_email import (
    build_subject,
    default_daily_doc_id,
    default_weekly_doc_id,
    send_summary_dogfood,
)
from services.summary.summary_markdown_email import (
    load_summary_email_bodies,
    markdown_to_email_text,
    summary_markdown_path,
)


def test_default_daily_doc_id_is_yesterday_jst():
    assert default_daily_doc_id(today_jst=date(2026, 7, 25)) == "2026-07-24"


def test_default_weekly_doc_id_is_previous_iso_week():
    # 2026-07-20 is Monday of 2026-W30 → previous week W29
    assert default_weekly_doc_id(today_jst=date(2026, 7, 20)) == "2026-W29"


def test_build_subject():
    assert (
        build_subject("daily", "jp", "2026-07-22")
        == "[Trends-dashboard][JP][daily] 2026-07-22"
    )


def test_summary_markdown_path_jp_us(tmp_path: Path):
    assert summary_markdown_path(
        "daily", "2026-07-22", region="jp", summaries_root=tmp_path
    ) == tmp_path / "daily" / "2026-07-22.md"
    assert summary_markdown_path(
        "daily", "2026-07-22", region="us", summaries_root=tmp_path
    ) == tmp_path / "daily" / "us" / "2026-07-22.md"


def test_load_summary_email_bodies_daily(tmp_path: Path):
    daily = tmp_path / "daily"
    daily.mkdir()
    (daily / "2026-07-22.md").write_text(
        "---\nstatus: draft\n---\n\n# Hello\n\n**bold** and [a](https://ex.com)\n",
        encoding="utf-8",
    )
    path, text, html = load_summary_email_bodies(
        "daily", "2026-07-22", region="jp", summaries_root=tmp_path
    )
    assert path.name == "2026-07-22.md"
    assert "status: draft" not in text
    assert "bold" in text
    assert "https://ex.com" in text
    assert "<h1>" in html
    assert '<a href="https://ex.com">a</a>' in html
    assert "<strong>bold</strong>" in html


def test_send_summary_dogfood_dry_run(monkeypatch):
    def fake_load(kind, doc_id, region="jp", **kw):
        return (
            Path(f"/tmp/{region}/{doc_id}.md"),
            markdown_to_email_text("# x\n"),
            "<html><body><h1>x</h1></body></html>",
        )

    monkeypatch.setattr(
        "services.summary.summary_dogfood_email.load_summary_email_bodies",
        fake_load,
    )
    results = send_summary_dogfood(
        kind="daily",
        doc_id="2026-07-22",
        regions=("jp", "us"),
        to_email="me@example.com",
        dry_run=True,
    )
    assert len(results) == 2
    assert all(r.ok and not r.skipped for r in results)
