"""Legal pages (privacy / terms public; SCT hidden until selling resumes)."""

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
    assert "/legal/privacy" in text
    assert "/legal/terms" in text
    # SCT is kept at URL but not linked from related-nav / public chrome
    assert 'href="/legal/sct"' not in text


def test_sct_is_noindex(client):
    text = client.get("/legal/sct").get_data(as_text=True)
    assert 'content="noindex, nofollow"' in text


def test_privacy_terms_are_indexable(client):
    for path in ("/legal/privacy", "/legal/terms"):
        text = client.get(path).get_data(as_text=True)
        assert 'content="index, follow"' in text


def test_legal_pages_avoid_ai_summary_label(client):
    for path in ("/legal/sct", "/legal/privacy", "/legal/terms"):
        text = client.get(path).get_data(as_text=True)
        assert "AI サマリー" not in text
        assert "AIサマリー" not in text


def test_sitemap_excludes_sct_includes_privacy_terms(client):
    res = client.get("/sitemap.xml")
    assert res.status_code == 200
    text = res.get_data(as_text=True)
    assert "/legal/sct" not in text
    assert "/legal/privacy" in text
    assert "/legal/terms" in text


def test_about_footer_hides_sct(client):
    text = client.get("/about").get_data(as_text=True)
    assert 'href="/legal/sct"' not in text
    assert 'href="/legal/privacy"' in text
    assert 'href="/legal/terms"' in text
