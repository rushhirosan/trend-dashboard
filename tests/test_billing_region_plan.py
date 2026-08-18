"""Tests for billing region_plan helpers."""

from services.billing.region_plan import normalize_region_plan, regions_for_plan


def test_normalize_region_plan_valid():
    assert normalize_region_plan("jp") == "jp"
    assert normalize_region_plan("US") == "us"
    assert normalize_region_plan("both") == "both"


def test_normalize_region_plan_invalid():
    assert normalize_region_plan("xx") is None
    assert normalize_region_plan("") == "jp"  # 省略時デフォルト


def test_regions_for_plan():
    assert regions_for_plan("jp") == ("jp",)
    assert regions_for_plan("us") == ("us",)
    assert regions_for_plan("both") == ("jp", "us")
