"""Gumroad の購入通知。

JP は月額メンバーシップ。請求（sale）のたびに約30日、配信対象にする。
解約通知では期限を延ばさない。支払い済みの期間は expires_at まで残る。
US は単品で、同じ sale 処理を使う。

Ping は application/x-www-form-urlencoded。price は USD セントなので金額判定には使わない。
署名は無い。Ping URL の token、seller_id、商品 ID が一致した sale だけを配信対象にする。
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Set, Tuple
from urllib.parse import urlparse

from config.app_config import AppConfig
from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

_REVOKE_RESOURCES = frozenset({"refund", "dispute"})
# 解約・更新・終了は sale ではない。再付与すると解約後に期限が伸びる。
_IGNORE_RESOURCES = frozenset({
    "dispute_won",
    "cancellation",
    "subscription_updated",
    "subscription_restarted",
    "subscription_ended",
})


def access_days() -> int:
    return max(1, int(AppConfig.GUMROAD_ACCESS_DAYS or 30))


def checkout_url(region: str) -> str:
    """Webhook が商品を識別できるときだけ、ダッシュボードに出す購入 URL。"""
    region_n = "us" if (region or "").strip().lower() == "us" else "jp"
    if not (AppConfig.GUMROAD_SELLER_ID or "").strip():
        return ""
    if not (AppConfig.GUMROAD_PING_TOKEN or "").strip():
        return ""
    if not _product_ids(region_n):
        return ""
    raw = AppConfig.GUMROAD_URL_US if region_n == "us" else AppConfig.GUMROAD_URL_JP
    return _https_gumroad_url(raw)


def handle_gumroad_ping(
    fields: Mapping[str, str],
    *,
    ping_token: str = "",
    subscriber_manager: Optional[AiSummarySubscriberManager] = None,
) -> Tuple[int, str]:
    """Gumroad Ping を処理し、(HTTP status, detail) を返す。"""
    expected_token = (AppConfig.GUMROAD_PING_TOKEN or "").strip()
    if not expected_token:
        return 503, "gumroad ping token not configured"
    provided = (ping_token or "").strip()
    if not provided or not hmac.compare_digest(provided, expected_token):
        return 401, "invalid ping token"

    expected_seller = (AppConfig.GUMROAD_SELLER_ID or "").strip()
    if not expected_seller:
        return 503, "gumroad seller not configured"

    seller_id = _field(fields, "seller_id")
    if seller_id != expected_seller:
        return 401, "invalid seller"

    if _is_test(fields) and not AppConfig.GUMROAD_ACCEPT_TEST:
        return 200, "ignored:test"

    resource = _field(fields, "resource_name").lower()
    if resource in _IGNORE_RESOURCES:
        return 200, f"ignored:{resource}"

    product_id = _field(fields, "product_id")
    short_id = _field(fields, "short_product_id")
    permalink = _field(fields, "product_permalink") or _field(fields, "permalink")
    region = _region_for_product(product_id, short_id, permalink)
    sale_id = _field(fields, "sale_id")
    mgr = subscriber_manager or AiSummarySubscriberManager()

    if resource in _REVOKE_RESOURCES or _is_truthy(_field(fields, "refunded")):
        if not sale_id:
            return 200, "ignored:refund_missing_sale"
        if not region and resource not in _REVOKE_RESOURCES:
            return 200, "ignored:product"
        if mgr.revoke_gumroad_sale(sale_id):
            logger.info("Gumroad refund revoked sale=%s", sale_id)
            return 200, "revoked"
        return 200, "revoke_noop"

    if region is None:
        return 200, "ignored:product"
    if not sale_id:
        return 200, "ignored:sale_id"

    email = _field(fields, "email").lower()
    if not AiSummarySubscriberManager.validate_email(email):
        logger.warning("Gumroad sale missing email sale=%s", sale_id)
        return 200, "ignored:email"

    expires_at = datetime.now(timezone.utc) + timedelta(days=access_days())
    ok, msg = mgr.grant_gumroad_access(
        email=email,
        region_plan=region,
        sale_id=sale_id,
        expires_at=expires_at,
    )
    if not ok:
        logger.error("Gumroad sale DB failed sale=%s: %s", sale_id, msg)
        return 500, f"upsert_failed:{msg}"
    logger.info("Gumroad sale %s region=%s sale=%s", msg, region, sale_id)
    return 200, "already_active" if msg == "already_active" else "activated"


def _field(fields: Mapping[str, str], key: str) -> str:
    value = fields.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _is_truthy(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def _is_test(fields: Mapping[str, str]) -> bool:
    return _is_truthy(_field(fields, "test"))


def _product_ids(region: str) -> Set[str]:
    raw = (
        AppConfig.GUMROAD_PRODUCT_ID_US
        if region == "us"
        else AppConfig.GUMROAD_PRODUCT_ID_JP
    )
    return {part.strip() for part in (raw or "").split(",") if part.strip()}


def _region_for_product(product_id: str, short_id: str, permalink: str = "") -> Optional[str]:
    incoming = {item for item in (product_id, short_id, permalink) if item}
    if not incoming:
        return None
    if incoming & _product_ids("jp"):
        return "jp"
    if incoming & _product_ids("us"):
        return "us"
    return None


def _https_gumroad_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return ""
    if host != "gumroad.com" and not host.endswith(".gumroad.com"):
        return ""
    return raw
