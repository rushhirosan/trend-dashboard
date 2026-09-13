"""Legal pages for PAY.JP / tokutei shotorihiki."""

import pytest

from app import create_app


@pytest.fixture
def client():
    app, _ = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize(
    "path,needle",
    [
        ("/legal/sct", "特定商取引法"),
        ("/legal/privacy", "プライバシーポリシー"),
        ("/legal/terms", "利用規約"),
    ],
)
def test_legal_pages_ok(client, path, needle):
    res = client.get(path)
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert needle in text
    assert "/legal/sct" in text
    assert "/legal/privacy" in text
    assert "/legal/terms" in text


def test_legal_pages_avoid_ai_summary_label(client):
    for path in ("/legal/sct", "/legal/privacy", "/legal/terms"):
        text = client.get(path).get_data(as_text=True)
        assert "AI サマリー" not in text
        assert "AIサマリー" not in text


def test_sitemap_includes_legal(client):
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "/legal/sct" in text
    assert "/legal/privacy" in text
    assert "/legal/terms" in text
