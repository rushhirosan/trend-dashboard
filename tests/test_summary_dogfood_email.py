"""Tests for summary dogfood email helpers."""

from datetime import date
from pathlib import Path

from services.summary.summary_dogfood_email import (
    DOGFOOD_BANNER,
    build_subject,
    default_daily_doc_id,
    default_weekly_doc_id,
    send_summary_dogfood,
)
from services.summary.summary_markdown_email import (
    append_summary_email_footer,
    dashboard_email_url,
    load_summary_email_bodies,
    markdown_to_email_text,
    summary_markdown_path,
    world_front_page_email_url,
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
    assert (
        build_subject("daily", "jp", "2026-07-22", cross_source=True)
        == "[Trends-dashboard][JP][daily] 2026-07-22（横断あり）"
    )
    assert (
        build_subject("daily", "us", "2026-07-22", cross_source=True)
        == "[Trends-dashboard][US][daily] 2026-07-22 (cross-source)"
    )


def test_summary_markdown_path_jp_us(tmp_path: Path):
    assert summary_markdown_path(
        "daily", "2026-07-22", region="jp", summaries_root=tmp_path
    ) == tmp_path / "daily" / "2026-07-22.md"
    assert summary_markdown_path(
        "daily", "2026-07-22", region="us", summaries_root=tmp_path
    ) == tmp_path / "daily" / "us" / "2026-07-22.md"


def _use_default_site_base(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TREND_DASHBOARD_BASE_URL", raising=False)


def test_load_summary_email_bodies_daily(tmp_path: Path, monkeypatch):
    _use_default_site_base(monkeypatch)
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
    # テキストパートはラベルのみ（長い URL を晒さない）。リンクは HTML 側。
    assert "https://ex.com" not in text
    assert " and a\n" in text or text.rstrip().endswith("and a")
    assert "<h1>" in html
    assert '<a href="https://ex.com">a</a>' in html
    assert "<strong>bold</strong>" in html
    assert "World Front Page" in text
    assert "g7-dashboard.vercel.app" in text
    assert "utm_medium=summary_email" in text
    assert "utm_content=daily" in html
    assert "G7・中国・インド" in html
    assert "ダッシュボードで最新データを見る" in text
    assert "ダッシュボードで最新データを見る</a>" in html
    assert "trends-dashboard.com/" in html


def test_load_summary_email_bodies_us_footer(tmp_path: Path, monkeypatch):
    _use_default_site_base(monkeypatch)
    daily = tmp_path / "daily" / "us"
    daily.mkdir(parents=True)
    (daily / "2026-07-22.md").write_text(
        "---\nstatus: draft\n---\n\n# Hello\n",
        encoding="utf-8",
    )
    _, text, html = load_summary_email_bodies(
        "daily", "2026-07-22", region="us", summaries_root=tmp_path
    )
    assert "Related: Top headlines from G7 countries" in text
    assert "G7, China & India" in html
    assert "utm_campaign=us" in html
    assert "See the latest on the dashboard" in text
    assert "trends-dashboard.com/us?" in html


def test_world_front_page_email_url():
    url = world_front_page_email_url(region="jp", kind="weekly")
    assert url.startswith("https://g7-dashboard.vercel.app/?")
    assert "utm_campaign=jp" in url
    assert "utm_content=weekly" in url


def test_dashboard_email_url(monkeypatch):
    _use_default_site_base(monkeypatch)
    jp = dashboard_email_url(region="jp", kind="daily")
    assert jp.startswith("https://trends-dashboard.com/?")
    assert "utm_medium=summary_email" in jp
    us = dashboard_email_url(region="us", kind="weekly")
    assert us.startswith("https://trends-dashboard.com/us?")
    assert "utm_content=weekly" in us


def test_append_summary_email_footer(monkeypatch):
    _use_default_site_base(monkeypatch)
    text, html = append_summary_email_footer(
        "body\n",
        "<html><body><h1>x</h1></body></html>",
        region="jp",
        kind="daily",
    )
    assert "World Front Page" in text
    assert "g7-dashboard.vercel.app" in text
    assert "World Front Page</a>" in html
    assert "ダッシュボードで最新データを見る</a>" in html
    assert "trends-dashboard.com/" in html
    assert html.index("ダッシュボードで最新データを見る") < html.index("World Front Page")
    assert html.index("<hr") < html.index("</body>")


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


def test_send_summary_dogfood_banner(monkeypatch):
    def fake_load(kind, doc_id, region="jp", **kw):
        return (
            Path(f"/tmp/{region}/{doc_id}.md"),
            "body text\n",
            "<html><body><h1>x</h1></body></html>",
        )

    monkeypatch.setattr(
        "services.summary.summary_dogfood_email.load_summary_email_bodies",
        fake_load,
    )
    sent = []

    class FakeEmail:
        def is_configured(self):
            return True

        def send_multipart(self, to, subject, html, text):
            sent.append({"to": to, "subject": subject, "html": html, "text": text})
            return True

    results = send_summary_dogfood(
        kind="daily",
        doc_id="2026-07-22",
        regions=("jp",),
        to_email="me@example.com",
        dry_run=False,
        email_service=FakeEmail(),
    )
    assert len(results) == 1 and results[0].ok
    assert DOGFOOD_BANNER == "【自分（開発者）宛専用 / Developer-only】"
    assert sent[0]["text"].startswith(DOGFOOD_BANNER)
    assert f"<em>{DOGFOOD_BANNER}</em>" in sent[0]["html"]
    assert "dogfood · draft OK" not in sent[0]["html"]
    assert "draft 可・自動送信" not in sent[0]["text"]
