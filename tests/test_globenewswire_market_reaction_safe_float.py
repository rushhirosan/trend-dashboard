"""GlobeNewswire × Market Reaction の NaN / Decimal ガード。"""

from decimal import Decimal

import math

from services.trends.base_trends_manager import (
    BaseTrendsManager,
    _safe_numeric_sort_value,
)
from services.trends.globenewswire_market_reaction_trends import _safe_float


def test_safe_float_nan_and_decimal():
    assert _safe_float(float("nan")) == 0.0
    assert _safe_float(float("inf")) == 0.0
    assert _safe_float(Decimal("NaN")) == 0.0
    assert _safe_float(Decimal("1.25")) == 1.25
    assert _safe_float(None) == 0.0
    assert _safe_float("3.5%") == 3.5
    assert _safe_float("bad") == 0.0


def test_safe_numeric_sort_value_handles_decimal_nan():
    assert _safe_numeric_sort_value(Decimal("NaN")) == 0.0
    assert _safe_numeric_sort_value(float("nan")) == 0.0
    assert _safe_numeric_sort_value(Decimal("12.3")) == 12.3


class _SortProbe(BaseTrendsManager):
    def __init__(self):
        # BaseTrendsManager.__init__ は DB 等を触るため、ソートだけ差し替え利用
        pass

    def _get_cache_key(self, *args, **kwargs):
        return "probe"

    def _get_from_cache(self, *args, **kwargs):
        return []

    def _save_to_cache(self, data, *args, **kwargs):
        return True

    def _clear_cache(self, *args, **kwargs):
        return True

    def _fetch_trends(self, *args, **kwargs):
        return {"success": True, "data": []}


def test_apply_default_sorting_reaction_score_with_decimal_nan():
    """キャッシュ由来 Decimal('NaN') でも InvalidOperation にならない。"""
    mgr = _SortProbe()
    data = [
        {"title": "a", "reaction_score": Decimal("NaN")},
        {"title": "b", "reaction_score": Decimal("5.0")},
        {"title": "c", "reaction_score": float("nan")},
        {"title": "d", "reaction_score": 3.2},
    ]
    sorted_data = mgr._apply_default_sorting(data, sort_key="reaction_score", reverse=True)
    scores = [x["reaction_score"] for x in sorted_data]
    # rank 再付与後も元値は残るが、ソート自体は完了していること
    assert len(sorted_data) == 4
    assert sorted_data[0]["title"] == "b"
    assert all(isinstance(x.get("rank"), int) for x in sorted_data)
    # NaN 同士の比較で落ちないことを明示
    assert any(isinstance(s, Decimal) and not s.is_finite() for s in scores) or any(
        isinstance(s, float) and not math.isfinite(s) for s in scores
    )
