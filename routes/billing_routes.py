"""Stripe Checkout / Webhook ルート（有料 AI サマリー）。"""

import hmac
import os

from flask import Blueprint, jsonify, render_template, request

from config.app_config import AppConfig
from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from services.billing.region_plan import normalize_region_plan
from services.billing.stripe_service import (
    checkout_enabled,
    create_checkout_session,
    handle_webhook_event,
)
from utils.logger_config import get_logger

logger = get_logger(__name__)

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/api/billing/ai-summary/checkout", methods=["POST"])
def ai_summary_checkout():
    """地域プランを選び Stripe Checkout へ。"""
    if not checkout_enabled():
        return jsonify({"success": False, "error": "決済は現在利用できません"}), 503

    data = request.get_json(silent=True) or {}
    region_plan = normalize_region_plan(
        data.get("region_plan"),
        default=(data.get("region") or "jp"),
    )
    if not region_plan:
        return jsonify({"success": False, "error": "region_plan が不正です"}), 400

    base = AppConfig.PUBLIC_BASE_URL.rstrip("/")
    success_url = f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/billing/cancel"

    ok, message, _session_id = create_checkout_session(
        region_plan=region_plan,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    if not ok:
        return jsonify({"success": False, "error": message}), 502
    return jsonify({"success": True, "url": message})


@billing_bp.route("/api/billing/stripe/webhook", methods=["POST"])
def stripe_webhook():
    """Stripe Webhook（raw body + 署名検証）。"""
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature")
    ok, message = handle_webhook_event(payload, sig)
    if not ok:
        logger.warning("Stripe webhook rejected: %s", message)
        status = 400 if message in ("invalid payload", "invalid signature") else 500
        return jsonify({"error": message}), status
    return jsonify({"received": True, "detail": message})


@billing_bp.route("/api/billing/ai-summary/subscribers", methods=["GET"])
def ai_summary_subscribers():
    """有効な有料購読者一覧（GHA 有料配信用）。

    認証: ``Authorization: Bearer $SUMMARY_UPSERT_TOKEN``（publish と同じ）。
    GHA から Fly Postgres に直接繋がらないため、アプリ経由で読む。
    """
    token = (os.getenv("SUMMARY_UPSERT_TOKEN") or "").strip()
    if not token:
        return jsonify({
            "success": False,
            "error": "SUMMARY_UPSERT_TOKEN が未設定のため、このエンドポイントは無効です",
        }), 503
    provided = request.headers.get("Authorization") or ""
    if not hmac.compare_digest(provided, f"Bearer {token}"):
        return jsonify({"success": False, "error": "unauthorized"}), 401

    rows = AiSummarySubscriberManager().list_all_active()
    return jsonify({
        "success": True,
        "subscribers": [
            {"email": r["email"], "region_plan": r["region_plan"]} for r in rows
        ],
    })


@billing_bp.route("/billing/success")
def billing_success():
    """Checkout 成功後の簡易ページ。"""
    return render_template("billing_success.html")


@billing_bp.route("/billing/cancel")
def billing_cancel():
    """Checkout キャンセル。"""
    return render_template("billing_cancel.html")
