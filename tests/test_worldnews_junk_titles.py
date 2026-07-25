# -*- coding: utf-8 -*-
"""World News: ログイン壁由来のゴミタイトル除外"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trends.worldnews_trends import WorldNewsTrendsManager


@pytest.fixture
def manager():
    return WorldNewsTrendsManager()


class TestIsJunkTitle:
    @pytest.mark.parametrize(
        "title",
        [
            "Log in",
            "log in",
            "Login",
            "Sign in",
            "Sign In",
            "signin",
            "Sign up",
            "ログイン",
            "Access Denied",
            "403",
            "Page Not Found",
            "Just a moment",
            "No Title",
            "  Log in  ",
        ],
    )
    def test_rejects_junk_titles(self, manager, title):
        assert manager._is_junk_title(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Silent Springs, Windswept Seas: Rachel Carson’s Environmental Vision",
            "How to log in securely to your bank",
            "Login page redesign trends in 2026",
            "最高気温40度以上「酷暑日」予想",
        ],
    )
    def test_keeps_real_headlines(self, manager, title):
        assert manager._is_junk_title(title) is False


class TestRemoveDuplicatesFiltersJunk:
    def test_drops_log_in_and_renumbers(self, manager):
        items = [
            {
                "rank": 1,
                "title": "Log in",
                "url": "https://events.yale.edu/event/silent-springs-windswept-seas-rachel-carsons-environmental-vision",
            },
            {
                "rank": 2,
                "title": "Can Benjamin Netanyahu Be Stopped?",
                "url": "https://newrepublic.com/article/213271/benjamin-netanyahu-election-knesset-october",
            },
            {
                "rank": 3,
                "title": "Sign in",
                "url": "https://example.com/gated",
            },
        ]
        cleaned = manager._remove_duplicates(items)
        assert len(cleaned) == 1
        assert cleaned[0]["title"] == "Can Benjamin Netanyahu Be Stopped?"
        assert cleaned[0]["rank"] == 1
