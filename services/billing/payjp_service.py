"""PAY.JP API v2 都度払い（AI サマリーお試し・JP・約30日）。

Checkout Session（hosted）でクレカ / PayPay を受け付け、
Webhook ``checkout.session.completed`` で購読者 DB に登録する。
v1 定期（Subscription）は本番では使わない（資産のみ）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from config.app_config import AppConfig
from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from utils.logger_config import get_logger

logger = get_logger(__name__)

DEFAULT_REGION_PLAN = "jp"
_V2_BASE = "https://api.pay.jp/v2"
_HTTP_TIMEOUT_SEC = 30


def payjp_configured() -> bool:
    return bool(AppConfig.PAYJP_SECRET_KEY) and AppConfig.PAYJP_TRIAL_AMOUNT_JPY > 0


def checkout_enabled() -> bool:
    if not AppConfig.ENABLE_AI_SUMMARY_CHECKOUT:
        return False
    return payjp_configured()


def trial_days() -> int:
    return max(1, int(AppConfig.PAYJP_TRIAL_DAYS or 30))


def trial_amount_jpy() -> int:
    return max(50, int(AppConfig.PAYJP_TRIAL_AMOUNT_JPY or 500))


def payment_method_types() -> List[str]:
    raw = (AppConfig.PAYJP_PAYMENT_METHOD_TYPES or "card,paypay").strip()
    types = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return types or ["card", "paypay"]


def _auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AppConfig.PAYJP_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _session_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """SDK ラッパー形 ``{data: ...}`` と直オブジェクトの両方に対応。"""
    nested = body.get("data")
    if isinstance(nested, dict):
        sid = nested.get("id") or ""
        if (
            nested.get("object") == "checkout.session"
            or nested.get("url")
            or (isinstance(sid, str) and sid.startswith("cs_"))
        ):
            return nested
    return body


def create_checkout_session(
    *,
    email: str,
) -> Tuple[bool, str, Optional[str]]:
    """
    Checkout Session を作成し、hosted Checkout URL を返す。

    Returns:
        (成功, メッセージまたはエラー, checkout_url)
    """
    email_n = (email or "").strip().lower()
    if not AiSummarySubscriberManager.validate_email(email_n):
        return False, "有効なメールアドレスが必要です", None
    if not payjp_configured():
        return False, "決済は現在利用できません", None

    base = AppConfig.PUBLIC_BASE_URL.rstrip("/")
    amount = trial_amount_jpy()
    days = trial_days()
    product_name = f"日本のサマリーお試し（約{days}日・日次＋週次）"

    line_item: Dict[str, Any] = {"quantity": 1}
    price_id = (AppConfig.PAYJP_PRICE_ID or "").strip()
    if price_id:
        line_item["price_id"] = price_id
    else:
        line_item["price_data"] = {
            "currency": "jpy",
            "unit_amount": amount,
            "product_data": {"name": product_name},
        }

    body: Dict[str, Any] = {
        "mode": "payment",
        "locale": "ja",
        "customer_email": email_n,
        "payment_method_types": payment_method_types(),
        "line_items": [line_item],
        "success_url": f"{base}/billing/success",
        "cancel_url": f"{base}/billing/cancel",
        "metadata": {
            "product": "ai_summary_trial",
            "region_plan": DEFAULT_REGION_PLAN,
            "email": email_n,
            "trial_days": str(days),
        },
    }

    try:
        res = requests.post(
            f"{_V2_BASE}/checkout/sessions",
            headers=_auth_headers(),
            json=body,
            timeout=_HTTP_TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        logger.error("❌ PAY.JP v2 Checkout Session 通信エラー: %s", e, exc_info=True)
        return False, "決済画面の生成に失敗しました。しばらくしてからお試しください。", None

    if res.status_code >= 400:
        logger.error(
            "❌ PAY.JP v2 Checkout Session 失敗 status=%s body=%s",
            res.status_code,
            res.text[:500],
        )
        return False, "決済画面の生成に失敗しました。しばらくしてからお試しください。", None

    try:
        payload = res.json()
    except ValueError:
        logger.error("❌ PAY.JP v2 Checkout Session 不正 JSON")
        return False, "決済画面の生成に失敗しました。しばらくしてからお試しください。", None

    session = _session_payload(payload if isinstance(payload, dict) else {})
    url = (session.get("url") or "").strip()
    if not url:
        logger.error("❌ PAY.JP v2 Checkout Session に url が無い: %s", session)
        return False, "決済画面の生成に失敗しました。しばらくしてからお試しください。", None

    return True, "ok", url


def handle_webhook_event(
    payload: Dict[str, Any],
    webhook_token_header: Optional[str],
    *,
    subscriber_manager: Optional[AiSummarySubscriberManager] = None,
) -> Tuple[bool, str]:
    """PAY.JP Webhook（JSON + X-Payjp-Webhook-Token）。"""
    expected = (AppConfig.PAYJP_WEBHOOK_TOKEN or "").strip()
    if not expected:
        return False, "webhook token not configured"
    provided = (webhook_token_header or "").strip()
    if not provided or provided != expected:
        return False, "invalid webhook token"

    event_type = (payload.get("type") or "").strip()
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    mgr = subscriber_manager or AiSummarySubscriberManager()

    if event_type == "checkout.session.completed":
        return _activate_from_checkout_session(data, mgr)

    # v1 定期資産向け（本番お試しでは使わないが、旧イベントが来ても壊さない）
    if event_type in ("subscription.deleted", "subscription.paused"):
        sub_id = data.get("id")
        if sub_id and mgr.deactivate_by_subscription_id(str(sub_id)):
            return True, "deactivated"
        return True, "deactivate_noop"

    return True, f"ignored:{event_type}"


def _email_from_checkout_session(session: Dict[str, Any]) -> str:
    meta = session.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    for key in ("email",):
        val = (meta.get(key) or "").strip().lower()
        if val:
            return val
    for key in ("customer_email",):
        val = (session.get(key) or "").strip().lower()
        if val:
            return val
    details = session.get("customer_details") or {}
    if isinstance(details, dict):
        val = (details.get("email") or "").strip().lower()
        if val:
            return val
    return ""


def _activate_from_checkout_session(
    session: Dict[str, Any],
    mgr: AiSummarySubscriberManager,
) -> Tuple[bool, str]:
    email = _email_from_checkout_session(session)
    if not email:
        logger.warning("checkout.session.completed: email 不明 session=%s", session.get("id"))
        return True, "checkout_missing_email"

    meta = session.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    region = (meta.get("region_plan") or DEFAULT_REGION_PLAN).strip().lower()
    if region not in ("jp", "us", "both"):
        region = DEFAULT_REGION_PLAN

    days = trial_days()
    try:
        days = max(1, int(meta.get("trial_days") or days))
    except (TypeError, ValueError):
        pass

    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    customer_id = session.get("customer_id") or session.get("customer")
    session_id = session.get("id")

    ok, msg = mgr.upsert_active(
        email=email,
        region_plan=region,
        payjp_customer_id=str(customer_id) if customer_id else None,
        payjp_checkout_session_id=str(session_id) if session_id else None,
        expires_at=expires_at,
    )
    if not ok:
        logger.error(
            "checkout.session.completed DB 失敗 email=%s session=%s: %s",
            email,
            session_id,
            msg,
        )
        return False, f"upsert_failed:{msg}"
    return True, "activated"
