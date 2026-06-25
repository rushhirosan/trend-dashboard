"""静的ファイル Cache-Control のユニットテスト（Phase1 パフォーマンス）"""

import pytest

from app import create_app


@pytest.fixture(scope="module")
def app_client():
    app, _scheduler = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_static_js_cache_control(app_client):
    res = app_client.get("/static/js/app.js")
    assert res.status_code == 200
    cc = res.headers.get("Cache-Control", "")
    assert "max-age=31536000" in cc
    assert "public" in cc
    assert "immutable" in cc
    assert "no-cache" not in cc


def test_static_css_cache_control(app_client):
    res = app_client.get("/static/css/main.css")
    assert res.status_code == 200
    cc = res.headers.get("Cache-Control", "")
    assert "max-age=31536000" in cc
    assert "no-cache" not in cc
