"""Billing API tests."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from routes.billing_routes import billing_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["PUBLIC_BASE_URL"] = "https://example.com"
    app.register_blueprint(billing_bp)
    with app.test_client() as c:
        yield c


@patch("routes.billing_routes.checkout_enabled", return_value=False)
def test_checkout_disabled(mock_enabled, client):
    res = client.post(
        "/api/billing/ai-summary/checkout",
        json={"region_plan": "jp"},
    )
    assert res.status_code == 503


@patch("routes.billing_routes.checkout_enabled", return_value=True)
@patch("routes.billing_routes.create_checkout_session")
def test_checkout_success(mock_create, mock_enabled, client):
    mock_create.return_value = (True, "https://checkout.stripe.test/session", "cs_test")

    res = client.post(
        "/api/billing/ai-summary/checkout",
        json={"region_plan": "both"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["url"] == "https://checkout.stripe.test/session"
    mock_create.assert_called_once()


@patch("routes.billing_routes.checkout_enabled", return_value=True)
def test_checkout_invalid_plan(mock_enabled, client):
    res = client.post(
        "/api/billing/ai-summary/checkout",
        json={"region_plan": "invalid"},
    )
    assert res.status_code == 400


@patch.dict("os.environ", {"SUMMARY_UPSERT_TOKEN": ""}, clear=False)
def test_subscribers_disabled(client):
    res = client.get("/api/billing/ai-summary/subscribers")
    assert res.status_code == 503


@patch.dict("os.environ", {"SUMMARY_UPSERT_TOKEN": "secret-token"}, clear=False)
def test_subscribers_unauthorized(client):
    res = client.get(
        "/api/billing/ai-summary/subscribers",
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 401


@patch.dict("os.environ", {"SUMMARY_UPSERT_TOKEN": "secret-token"}, clear=False)
@patch("routes.billing_routes.AiSummarySubscriberManager")
def test_subscribers_ok(mock_mgr_cls, client):
    mock_mgr_cls.return_value.list_all_active.return_value = [
        {"email": "a@example.com", "region_plan": "jp"},
        {"email": "b@example.com", "region_plan": "both"},
    ]
    res = client.get(
        "/api/billing/ai-summary/subscribers",
        headers={"Authorization": "Bearer secret-token"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["subscribers"]) == 2


@patch("routes.billing_routes.handle_webhook_event")
def test_stripe_webhook_ok(mock_handle, client):
    mock_handle.return_value = (True, "ok")
    res = client.post(
        "/api/billing/stripe/webhook",
        data=b"{}",
        headers={"Stripe-Signature": "sig"},
    )
    assert res.status_code == 200
    mock_handle.assert_called_once()
