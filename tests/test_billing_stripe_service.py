"""Stripe webhook handler tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.billing.stripe_service import (
    _as_dict,
    _checkout_disclaimer,
    create_checkout_session,
    handle_webhook_event,
)


def test_as_dict_from_stripe_like_object():
    obj = SimpleNamespace(to_dict=lambda: {"type": "checkout.session.completed"})
    assert _as_dict(obj)["type"] == "checkout.session.completed"


def test_checkout_disclaimer_jp_and_us():
    jp = _checkout_disclaimer("jp")
    us = _checkout_disclaimer("us")
    assert "目標時刻" in jp
    assert "翌月無料" in jp
    assert "targets" in us
    assert "free month" in us


@patch("services.billing.stripe_service.AppConfig")
@patch("services.billing.stripe_service.stripe.checkout.Session.create")
def test_create_checkout_session_includes_disclaimer(mock_create, mock_config):
    mock_config.STRIPE_SECRET_KEY = "sk_test"
    mock_config.STRIPE_PRICE_ID = "price_test"
    mock_create.return_value = SimpleNamespace(
        url="https://checkout.stripe.test/session",
        id="cs_test",
    )

    ok, url, session_id = create_checkout_session(
        region_plan="jp",
        success_url="https://example.com/ok",
        cancel_url="https://example.com/cancel",
    )
    assert ok is True
    assert session_id == "cs_test"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["locale"] == "ja"
    assert "目標時刻" in kwargs["custom_text"]["submit"]["message"]


@patch("services.billing.stripe_service.AppConfig")
@patch("services.billing.stripe_service.stripe.Webhook.construct_event")
def test_checkout_session_completed_upserts(mock_construct, mock_config):
    mock_config.STRIPE_WEBHOOK_SECRET = "whsec_test"

    mock_construct.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "subscription",
                "id": "cs_test",
                "customer": "cus_test",
                "subscription": "sub_test",
                "customer_details": {"email": "buyer@example.com"},
                "metadata": {"region_plan": "both"},
            }
        },
    }

    mgr = MagicMock()
    mgr.upsert_active.return_value = (True, "ok")

    ok, msg = handle_webhook_event(b"{}", "sig", subscriber_manager=mgr)
    assert ok is True
    mgr.upsert_active.assert_called_once_with(
        email="buyer@example.com",
        region_plan="both",
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test",
    )


@patch("services.billing.stripe_service.AppConfig")
@patch("services.billing.stripe_service.stripe.Webhook.construct_event")
def test_checkout_session_completed_upserts_stripe_object(mock_construct, mock_config):
    """construct_event が StripeObject を返す場合も dict 化して処理する。"""
    mock_config.STRIPE_WEBHOOK_SECRET = "whsec_test"

    session = SimpleNamespace(
        to_dict=lambda: {
            "mode": "subscription",
            "id": "cs_test",
            "customer": "cus_test",
            "subscription": "sub_test",
            "customer_details": {"email": "buyer@example.com"},
            "metadata": {"region_plan": "jp"},
        }
    )
    event = SimpleNamespace(
        to_dict=lambda: {
            "type": "checkout.session.completed",
            "data": {"object": session.to_dict()},
        }
    )
    mock_construct.return_value = event

    mgr = MagicMock()
    mgr.upsert_active.return_value = (True, "ok")

    ok, _msg = handle_webhook_event(b"{}", "sig", subscriber_manager=mgr)
    assert ok is True
    mgr.upsert_active.assert_called_once()


@patch("services.billing.stripe_service.AppConfig")
@patch("services.billing.stripe_service.stripe.Webhook.construct_event")
def test_subscription_deleted_deactivates(mock_construct, mock_config):
    mock_config.STRIPE_WEBHOOK_SECRET = "whsec_test"

    mock_construct.return_value = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_test", "status": "canceled"}},
    }

    mgr = MagicMock()
    mgr.deactivate_by_subscription_id.return_value = True

    ok, msg = handle_webhook_event(b"{}", "sig", subscriber_manager=mgr)
    assert ok is True
    mgr.deactivate_by_subscription_id.assert_called_once_with("sub_test")
