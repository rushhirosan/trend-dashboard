"""HTTP tests for billing routes (PAY.JP v2)."""

from unittest.mock import patch

import pytest
from flask import Flask

from routes.billing_routes import billing_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(billing_bp)
    return app.test_client()


@patch("routes.billing_routes.checkout_enabled", return_value=False)
def test_subscribe_disabled(mock_enabled, client):
    res = client.post(
        "/api/billing/ai-summary/subscribe",
        json={"email": "a@b.com"},
    )
    assert res.status_code == 503


@patch("routes.billing_routes.checkout_enabled", return_value=True)
@patch("routes.billing_routes.trial_days", return_value=30)
@patch("routes.billing_routes.trial_amount_jpy", return_value=500)
@patch("routes.billing_routes.create_checkout_session")
def test_subscribe_ok(mock_create, mock_amount, mock_days, mock_enabled, client):
    mock_create.return_value = (True, "ok", "https://checkout.pay.jp/cs_x")
    res = client.post(
        "/api/billing/ai-summary/subscribe",
        json={"email": "a@b.com"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["redirect_url"] == "https://checkout.pay.jp/cs_x"
    assert data["amount_jpy"] == 500
    mock_create.assert_called_once()


@patch("routes.billing_routes.checkout_enabled", return_value=True)
@patch("routes.billing_routes.create_checkout_session")
def test_subscribe_bad_email(mock_create, mock_enabled, client):
    mock_create.return_value = (False, "有効なメールアドレスが必要です", None)
    res = client.post(
        "/api/billing/ai-summary/subscribe",
        json={"email": "bad"},
    )
    assert res.status_code == 400


def test_subscribers_requires_token(client):
    res = client.get("/api/billing/ai-summary/subscribers")
    assert res.status_code in (401, 503)


@patch.dict("os.environ", {"SUMMARY_UPSERT_TOKEN": "secret"}, clear=False)
@patch("routes.billing_routes.AiSummarySubscriberManager")
def test_subscribers_ok(mock_mgr_cls, client):
    mock_mgr_cls.return_value.list_all_active.return_value = [
        {"email": "a@b.com", "region_plan": "jp"},
    ]
    res = client.get(
        "/api/billing/ai-summary/subscribers",
        headers={"Authorization": "Bearer secret"},
    )
    assert res.status_code == 200
    assert res.get_json()["subscribers"][0]["email"] == "a@b.com"


@patch("routes.billing_routes.handle_webhook_event")
def test_payjp_webhook_ok(mock_handle, client):
    mock_handle.return_value = (True, "activated")
    res = client.post(
        "/api/billing/payjp/webhook",
        json={"type": "checkout.session.completed", "data": {"id": "cs_1"}},
        headers={"X-Payjp-Webhook-Token": "whook_x"},
    )
    assert res.status_code == 200
    assert res.get_json()["received"] is True
