"""有料サマリーの地域プラン（配信オプション）。"""

from __future__ import annotations

from typing import Sequence, Tuple

VALID_REGION_PLANS: Tuple[str, ...] = ("jp", "us", "both")


def normalize_region_plan(value: str | None, *, default: str = "jp") -> str | None:
    """有効な region_plan を返す。無効なら None。"""
    plan = (value or "").strip().lower()
    if plan in VALID_REGION_PLANS:
        return plan
    if not value and default in VALID_REGION_PLANS:
        return default
    return None


def regions_for_plan(region_plan: str) -> Sequence[str]:
    """配信対象の地域コード（jp/us）。"""
    plan = normalize_region_plan(region_plan)
    if plan == "us":
        return ("us",)
    if plan == "both":
        return ("jp", "us")
    return ("jp",)
