"""有料 AI サマリー課金ルート（PAY.JP v2 お試し・JP）。"""

import hmac
import os

from flask import Blueprint, jsonify, render_template, request

from config.app_config import AppConfig
from services.billing.ai_summary_subscriber_manager import AiSummarySubscriberManager
from services.billing.payjp_service import (
    checkout_enabled,
    create_checkout_session,
    handle_webhook_event,
    trial_amount_jpy,
    trial_days,
)
from utils.logger_config import get_logger

logger = get_logger(__name__)

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/api/billing/ai-summary/subscribe", methods=["POST"])
def ai_summary_subscribe():
    """メールアドレスから Checkout Session を作り、PAY.JP 決済 URL を返す。"""
    if not checkout_enabled():
        return jsonify({"success": False, "error": "決済は現在利用できません"}), 503

    data = request.get_json(silent=True) or {}
    email = data.get("email") or ""

    ok, message, checkout_url = create_checkout_session(email=email)
    if not ok or not checkout_url:
        return jsonify({"success": False, "error": message}), 400
    return jsonify({
        "success": True,
        "message": message,
        "redirect_url": checkout_url,
        "trial_days": trial_days(),
        "amount_jpy": trial_amount_jpy(),
    })


@billing_bp.route("/api/billing/payjp/webhook", methods=["POST"])
def payjp_webhook():
    """PAY.JP Webhook（JSON + X-Payjp-Webhook-Token）。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid payload"}), 400
    token = request.headers.get("X-Payjp-Webhook-Token")
    ok, message = handle_webhook_event(payload, token)
    if not ok:
        logger.warning("PAY.JP webhook rejected: %s", message)
        status = 400 if "token" in message or "payload" in message else 500
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
    """お試し購入完了の簡易ページ（Webhook 反映まで数分かかる場合あり）。"""
    return render_template("billing_success.html")


@billing_bp.route("/billing/cancel")
def billing_cancel():
    """決済キャンセル（Checkout 中断など）。"""
    return render_template("billing_cancel.html")
