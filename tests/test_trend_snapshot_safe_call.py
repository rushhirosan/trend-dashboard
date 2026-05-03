"""trend_snapshot_service._safe_call_series の success / 旧形式互換"""

from services.trend_snapshot_service import _safe_call_series


def test_success_true_with_list():
    sk, items = _safe_call_series(
        "x",
        lambda: {
            "success": True,
            "data": [{"title": "A", "rank": 1}],
        },
        10,
    )
    assert sk == "x"
    assert len(items) == 1
    assert items[0]["t"] == "A"


def test_success_omitted_with_data_list_legacy():
    sk, items = _safe_call_series(
        "legacy",
        lambda: {"data": [{"keyword": "kw", "rank": 2}]},
        10,
    )
    assert len(items) == 1
    assert items[0]["t"] == "kw"


def test_success_false_skipped():
    sk, items = _safe_call_series(
        "f",
        lambda: {"success": False, "data": [{"title": "no"}]},
        10,
    )
    assert items == []


def test_error_only_skipped():
    sk, items = _safe_call_series(
        "e",
        lambda: {"error": "boom"},
        10,
    )
    assert items == []
