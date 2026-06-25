"""refresh subprocess 向けの部分マネージャー初期化。"""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("yfinance")
pytest.importorskip("yahooquery")

from managers import trend_managers as tm


def test_initialize_managers_filters_keys():
    created = []

    def fake_init(key, cls, name):
        created.append(key)
        return MagicMock(name=key)

    with patch.object(tm, "_initialize_single_manager", side_effect=fake_init):
        managers = tm.initialize_managers(keys=frozenset({"google", "kkj"}))
    assert set(managers.keys()) == {"google", "kkj"}
    assert created == ["google", "kkj"]


def test_managers_for_refresh_jp_kkj_chunk_only():
    created = []

    def fake_init(key, cls, name):
        created.append(key)
        return MagicMock(name=key)

    with patch.object(tm, "_initialize_single_manager", side_effect=fake_init):
        managers = tm.managers_for_refresh("jp", jp_chunk=6, jp_chunks=6)
    assert set(managers.keys()) == {"kkj"}
    assert created == ["kkj"]


def test_managers_for_refresh_us_includes_ebay_categories():
    created = []

    def fake_init(key, cls, name):
        m = MagicMock(name=key)
        if key == "ebay":
            m.get_available_categories.return_value = ["a", "b"]
        created.append(key)
        return m

    with patch.object(tm, "_initialize_single_manager", side_effect=fake_init):
        managers = tm.managers_for_refresh("us")
    assert "ebay" in managers
    assert "google" in managers
    assert created[0] == "ebay"
