"""Stripe Checkout / Webhook（有料 AI サマリー）。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import stripe

from config.app_config import AppConfig
from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from services.billing.region_plan import normalize_region_plan
from utils.logger_config import get_logger

logger = get_logger(__name__)


def stripe_configured() -> bool:
    return bool(AppConfig.STRIPE_SECRET_KEY and AppConfig.STRIPE_PRICE_ID)


def checkout_enabled() -> bool:
    if not AppConfig.ENABLE_AI_SUMMARY_CHECKOUT:
        return False
    return stripe_configured()


def _checkout_disclaimer(region_plan: str) -> str:
    """Stripe Checkout の submit 付近に出す免責（BACKLOG の商品文言と揃える）。"""
    if region_plan == "us":
        return (
            "Delivery times are targets (daily 7:30 JST, weekly Mondays 8:00 JST; "
            "delay caps apply). Gaps, delays, or missing sources can happen. "
            "Significant outages: a free month or a refund. Inbox delivery is not guaranteed."
        )
    return (
        "配信は目標時刻です（日次 7:30 JST、週次月曜 8:00 JST。遅延上限あり）。"
        "外部データや生成処理の都合で、欠損・遅延・欠配がありえます。"
        "重大な欠配は翌月無料または返金で対応します。メール環境による未到達は保証できません。"
    )


def _as_dict(obj: Any) -> Dict[str, Any]:
    """StripeObject / dict を plain dict に正規化（.get() 不可な StripeObject 対策）。"""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return {}


def create_checkout_session(
    *,
    region_plan: str,
    success_url: str,
    cancel_url: str,
) -> Tuple[bool, str, Optional[str]]:
    """
    サブスク Checkout Session を作成する。

    Returns:
        (成功, メッセージまたは checkout URL, session_id)
    """
    plan = normalize_region_plan(region_plan)
    if not plan:
        return False, "region_plan が不正です", None
    if not stripe_configured():
        return False, "決済は現在利用できません", None

    stripe.api_key = AppConfig.STRIPE_SECRET_KEY
    locale = "en" if plan == "us" else "ja"
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": AppConfig.STRIPE_PRICE_ID, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            locale=locale,
            metadata={"region_plan": plan},
            subscription_data={"metadata": {"region_plan": plan}},
            custom_text={
                "submit": {"message": _checkout_disclaimer(plan)},
            },
        )
        url = session.url or ""
        session_id = session.id
        if not url:
            return False, "Checkout URL の取得に失敗しました", None
        return True, url, session_id
    except stripe.StripeError as e:
        logger.error("❌ Stripe Checkout 作成エラー: %s", e, exc_info=True)
        return False, "決済セッションの作成に失敗しました", None


def handle_webhook_event(
    payload: bytes,
    sig_header: Optional[str],
    *,
    subscriber_manager: Optional[AiSummarySubscriberManager] = None,
) -> Tuple[bool, str]:
    """Stripe Webhook を処理する。"""
    secret = (AppConfig.STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret:
        return False, "webhook secret not configured"

    mgr = subscriber_manager or AiSummarySubscriberManager()

    try:
        event = stripe.Webhook.construct_event(payload, sig_header or "", secret)
    except ValueError:
        return False, "invalid payload"
    except stripe.SignatureVerificationError:
        return False, "invalid signature"

    event_d = _as_dict(event)
    event_type = event_d.get("type", "")
    data = _as_dict(event_d.get("data"))
    data_object = _as_dict(data.get("object"))

    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(data_object, mgr)
    if event_type in (
        "customer.subscription.deleted",
        "customer.subscription.updated",
    ):
        return _handle_subscription_lifecycle(event_type, data_object, mgr)

    return True, f"ignored:{event_type}"


def _extract_email(session: Dict[str, Any]) -> str:
    details = session.get("customer_details") or {}
    if not isinstance(details, dict):
        details = _as_dict(details)
    email = (details.get("email") or session.get("customer_email") or "").strip()
    return email.lower()


def _extract_region_plan(session: Dict[str, Any]) -> Optional[str]:
    meta = session.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = _as_dict(meta)
    return normalize_region_plan(meta.get("region_plan"))


def _handle_checkout_completed(
    session: Dict[str, Any],
    mgr: AiSummarySubscriberManager,
) -> Tuple[bool, str]:
    if session.get("mode") != "subscription":
        return True, "ignored:non_subscription_checkout"

    email = _extract_email(session)
    region_plan = _extract_region_plan(session)
    if not email or not region_plan:
        logger.warning(
            "checkout.session.completed: missing email or region_plan session=%s",
            session.get("id"),
        )
        return False, "missing email or region_plan"

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    ok, msg = mgr.upsert_active(
        email=email,
        region_plan=region_plan,
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
    )
    return ok, msg if ok else f"upsert_failed:{msg}"


def _handle_subscription_lifecycle(
    event_type: str,
    sub: Dict[str, Any],
    mgr: AiSummarySubscriberManager,
) -> Tuple[bool, str]:
    sub_id = sub.get("id")
    status = (sub.get("status") or "").lower()

    if event_type == "customer.subscription.deleted" or status in (
        "canceled",
        "unpaid",
        "incomplete_expired",
    ):
        if sub_id and mgr.deactivate_by_subscription_id(str(sub_id)):
            return True, "deactivated"
        return True, "deactivate_noop"

    if status in ("active", "trialing"):
        meta = sub.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = _as_dict(meta)
        region_plan = normalize_region_plan(meta.get("region_plan"))
        if not region_plan or not sub_id:
            return True, "subscription_active_no_update"

        # メールは Checkout 時に取っている。プラン変更は後続対応。
        return True, "subscription_active"

    return True, f"ignored:{event_type}:{status}"
