"""Tests for article URL helpers in scripts/snapshot_rising.py."""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "snapshot_rising.py"


@pytest.fixture(scope="module")
def sr():
    spec = importlib.util.spec_from_file_location("snapshot_rising", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_article_url_for_rising_uses_snapshot_u(sr):
    bundle = {
        "19": {
            "zenn_jp": [{"t": "Claude Code Tips", "r": 1, "u": "https://zenn.dev/articles/abc"}],
        },
    }
    url = sr.article_url_for_rising(bundle, "zenn_jp", "Claude Code Tips")
    assert url == "https://zenn.dev/articles/abc"


def test_article_url_for_rising_fallback_search(sr):
    bundle = {"19": {"google_trends_jp": [{"t": "Some Topic", "r": 1}]}}
    url = sr.article_url_for_rising(bundle, "google_trends_jp", "Some Topic")
    assert url.startswith("https://www.google.com/search?q=")


def test_fallback_search_url_truncates_long_label(sr):
    from urllib.parse import unquote_plus, urlparse, parse_qs

    long_title = "あ" * 120
    url = sr.fallback_search_url(long_title)
    assert url.startswith("https://www.google.com/search?q=")
    q = parse_qs(urlparse(url).query)["q"][0]
    assert len(q) <= sr._FALLBACK_SEARCH_Q_MAX
    assert len(unquote_plus(url)) < len(long_title) + 80
