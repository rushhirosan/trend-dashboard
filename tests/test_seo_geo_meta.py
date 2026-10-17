"""SEO / GEO: head・llms.txt・robots（ダッシュボード UI 非接触の範囲）"""

from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture(scope="module")
def app_client():
    app, _scheduler = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_llms_txt_contains_core_pages(app_client):
    res = app_client.get("/llms.txt")
    assert res.status_code == 200
    assert res.mimetype.startswith("text/plain")
    text = res.get_data(as_text=True)
    assert "Trends Dashboard" in text
    assert "/us" in text
    assert "/about" in text
    assert "World Front Page" in text
    assert "g7-dashboard.vercel.app" in text
    assert "いまの順位" in text
    assert "Current U.S. trend" in text


def test_llms_txt_lists_recent_summary_urls(app_client):
    fake_daily = [("2026-07-28", None)]
    fake_weekly = [("2026-W30", None)]
    with (
        patch(
            "services.summary.summary_pages.list_published_daily",
            side_effect=lambda **kw: fake_daily if kw.get("region") == "jp" else [],
        ),
        patch(
            "services.summary.summary_pages.list_published_weekly",
            side_effect=lambda **kw: fake_weekly if kw.get("region") == "jp" else [],
        ),
    ):
        res = app_client.get("/llms.txt")
    text = res.get_data(as_text=True)
    assert "/summaries/daily/2026-07-28" in text
    assert "/summaries/weekly/2026-W30" in text


def test_robots_txt_mentions_llms(app_client):
    res = app_client.get("/robots.txt")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "Sitemap:" in text
    assert "llms.txt" in text


def test_jp_index_head_title_without_body_copy_change(app_client):
    """SERP向け title は「いまの順位」。先頭にサーバー描画の1位文。長い説明パネルは出さない。"""
    res = app_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<title>いまの日本トレンド順位 | トレンドダッシュボード</title>" in html
    assert 'property="og:title" content="いまの日本トレンド順位 | トレンドダッシュボード"' in html
    assert 'name="twitter:title" content="いまの日本トレンド順位 | トレンドダッシュボード"' in html
    assert 'id="now-ranking"' in html
    assert "日本のトレンド順位" in html or "1位は「" in html
    assert "JavaScript を有効にしてください" not in html
    assert 'href="/llms.txt"' in html or 'href="' in html and "/llms.txt" in html
    assert 'id="about-trends-dashboard"' not in html
    assert "このページで分かること" not in html
    assert "このサイトについて" in html
    # FAQ セクションは about のみ（トップに出さない）
    assert 'id="faq"' not in html


def test_us_index_head_title_for_gsc_queries(app_client):
    """英語タイトルは current U.S. trend ranks。先頭にサーバー描画の #1。"""
    res = app_client.get("/us")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<title>Current U.S. trend ranks | Trends Dashboard</title>" in html
    assert "Current U.S. trend" in html
    assert 'id="now-ranking"' in html
    assert "Enable JavaScript" not in html
    assert 'property="og:title" content="Current U.S. trend ranks | Trends Dashboard"' in html
    assert "What this page covers" not in html
    assert 'id="faq"' not in html


def test_about_has_faq_schema(app_client):
    res = app_client.get("/about")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '"@type": "FAQPage"' in html
    assert 'id="faq"' in html
    assert "World Front Page" in html


def test_data_status_redirects_to_about(app_client):
    res = app_client.get("/data-status", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers.get("Location", "").endswith("/about")


def test_sitemap_omits_data_status(app_client):
    res = app_client.get("/sitemap.xml")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "/data-status" not in text
    assert "/about" in text


def test_llms_txt_omits_data_status(app_client):
    res = app_client.get("/llms.txt")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "/data-status" not in text
    assert "/about" in text
