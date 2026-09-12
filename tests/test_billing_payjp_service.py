"""Tests for PAY.JP v2 billing service."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.billing.payjp_service import (
    checkout_enabled,
    create_checkout_session,
    handle_webhook_event,
)


@patch("services.billing.payjp_service.AppConfig")
def test_checkout_enabled_requires_secret_and_amount(mock_config):
    mock_config.ENABLE_AI_SUMMARY_CHECKOUT = True
    mock_config.PAYJP_SECRET_KEY = "sk_test"
    mock_config.PAYJP_TRIAL_AMOUNT_JPY = 500
    assert checkout_enabled() is True

    mock_config.PAYJP_SECRET_KEY = ""
    assert checkout_enabled() is False


@patch("services.billing.payjp_service.AppConfig")
@patch("services.billing.payjp_service.requests.post")
def test_create_checkout_session_returns_url(mock_post, mock_config):
    mock_config.PAYJP_SECRET_KEY = "sk_test"
    mock_config.PAYJP_TRIAL_AMOUNT_JPY = 500
    mock_config.PAYJP_TRIAL_DAYS = 30
    mock_config.PAYJP_PRICE_ID = ""
    mock_config.PAYJP_PAYMENT_METHOD_TYPES = "card,paypay"
    mock_config.PUBLIC_BASE_URL = "https://example.com"

    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = {
        "id": "cs_test",
        "object": "checkout.session",
        "url": "https://checkout.pay.jp/cs_test",
    }
    mock_post.return_value = mock_res

    ok, msg, url = create_checkout_session(email="user@example.com")
    assert ok is True
    assert url == "https://checkout.pay.jp/cs_test"
    body = mock_post.call_args.kwargs["json"]
    assert body["mode"] == "payment"
    assert body["customer_email"] == "user@example.com"
    assert "paypay" in body["payment_method_types"]
    assert body["line_items"][0]["price_data"]["unit_amount"] == 500


@patch("services.billing.payjp_service.AppConfig")
def test_webhook_rejects_bad_token(mock_config):
    mock_config.PAYJP_WEBHOOK_TOKEN = "whook_expected"
    ok, msg = handle_webhook_event(
        {"type": "checkout.session.completed", "data": {"id": "cs_x"}},
        "whook_wrong",
    )
    assert ok is False
    assert "token" in msg


@patch("services.billing.payjp_service.AppConfig")
def test_webhook_checkout_completed_upserts(mock_config):
    mock_config.PAYJP_WEBHOOK_TOKEN = "whook_expected"
    mock_config.PAYJP_TRIAL_DAYS = 30
    mgr = MagicMock()
    mgr.upsert_active.return_value = (True, "購読を登録しました")

    ok, msg = handle_webhook_event(
        {
            "type": "checkout.session.completed",
            "data": {
                "id": "cs_1",
                "customer_email": "buyer@example.com",
                "customer_id": "cus_1",
                "metadata": {"region_plan": "jp", "trial_days": "30"},
            },
        },
        "whook_expected",
        subscriber_manager=mgr,
    )
    assert ok is True
    assert msg == "activated"
    kwargs = mgr.upsert_active.call_args.kwargs
    assert kwargs["email"] == "buyer@example.com"
    assert kwargs["region_plan"] == "jp"
    assert kwargs["payjp_checkout_session_id"] == "cs_1"
    assert isinstance(kwargs["expires_at"], datetime)
    assert kwargs["expires_at"].tzinfo == timezone.utc
