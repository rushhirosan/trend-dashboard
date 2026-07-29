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
    """タブ用 title は短く、og/twitter は長め。body SEO 説明は引き続き非表示（d-none）。"""
    res = app_client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "<title>トレンドダッシュボード</title>" in html
    assert 'property="og:title" content="日本のトレンドを20ソース横断比較 | トレンドダッシュボード"' in html
    assert 'name="twitter:title" content="日本のトレンドを20ソース横断比較 | トレンドダッシュボード"' in html
    assert 'href="/llms.txt"' in html or 'href="' in html and "/llms.txt" in html
    assert 'id="about-trends-dashboard"' in html
    assert "d-none" in html
    # FAQ セクションは about のみ（トップに出さない）
    assert 'id="faq"' not in html


def test_about_has_faq_schema(app_client):
    res = app_client.get("/about")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert '"@type": "FAQPage"' in html
    assert 'id="faq"' in html
    assert "World Front Page" in html
