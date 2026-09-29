"""Gumroad Ping → 30日分の配信対象。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from flask import Flask, render_template

from routes.billing_routes import billing_bp
from services.billing.gumroad_service import checkout_url, handle_gumroad_ping

_TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _ready(mock_config):
    mock_config.GUMROAD_SELLER_ID = "seller_1"
    mock_config.GUMROAD_PING_TOKEN = "ping-secret"
    mock_config.GUMROAD_PRODUCT_ID_JP = "short_jp"
    mock_config.GUMROAD_PRODUCT_ID_US = "short_us"
    mock_config.GUMROAD_URL_JP = "https://gumroad.com/l/jp-summary"
    mock_config.GUMROAD_URL_US = "https://gumroad.com/l/us-summary"
    mock_config.GUMROAD_ACCEPT_TEST = False
    mock_config.GUMROAD_ACCESS_DAYS = 30


def _sale(**overrides):
    fields = {
        "seller_id": "seller_1",
        "product_id": "long_jp",
        "short_product_id": "short_jp",
        "email": "reader@example.com",
        "sale_id": "sale_1",
        "resource_name": "sale",
        "price": "320",
    }
    fields.update(overrides)
    return fields


@patch("services.billing.gumroad_service.AppConfig")
def test_checkout_url_requires_token_seller_and_product(mock_config):
    _ready(mock_config)
    assert checkout_url("jp") == "https://gumroad.com/l/jp-summary"
    assert checkout_url("us") == "https://gumroad.com/l/us-summary"

    mock_config.GUMROAD_PING_TOKEN = ""
    assert checkout_url("jp") == ""

    _ready(mock_config)
    mock_config.GUMROAD_URL_JP = "http://gumroad.com/l/jp-summary"
    assert checkout_url("jp") == ""

    mock_config.GUMROAD_URL_JP = "https://evil.example/l/jp"
    assert checkout_url("jp") == ""


@patch("services.billing.gumroad_service.AppConfig")
def test_ping_rejects_bad_token(mock_config):
    _ready(mock_config)
    status, detail = handle_gumroad_ping(_sale(), ping_token="nope")
    assert status == 401
    assert detail == "invalid ping token"


@patch("services.billing.gumroad_service.AppConfig")
def test_ping_rejects_bad_seller(mock_config):
    _ready(mock_config)
    status, detail = handle_gumroad_ping(
        _sale(seller_id="other"),
        ping_token="ping-secret",
    )
    assert status == 401
    assert detail == "invalid seller"


@patch("services.billing.gumroad_service.AppConfig")
def test_ping_ignores_other_products_and_tests(mock_config):
    _ready(mock_config)
    status, detail = handle_gumroad_ping(
        _sale(product_id="other", short_product_id="other"),
        ping_token="ping-secret",
    )
    assert (status, detail) == (200, "ignored:product")

    status, detail = handle_gumroad_ping(
        _sale(test="true"),
        ping_token="ping-secret",
    )
    assert (status, detail) == (200, "ignored:test")


@patch("services.billing.gumroad_service.AppConfig")
def test_sale_grants_thirty_days_for_matching_product(mock_config):
    _ready(mock_config)
    mgr = MagicMock()
    mgr.grant_gumroad_access.return_value = (True, "購読を登録しました")
    status, detail = handle_gumroad_ping(
        _sale(product_id="other", short_product_id="other", product_permalink="short_jp"),
        ping_token="ping-secret",
        subscriber_manager=mgr,
    )
    assert (status, detail) == (200, "activated")
    kwargs = mgr.grant_gumroad_access.call_args.kwargs
    assert kwargs["email"] == "reader@example.com"
    assert kwargs["region_plan"] == "jp"
    assert kwargs["sale_id"] == "sale_1"
    assert kwargs["expires_at"] is not None


@patch("services.billing.gumroad_service.AppConfig")
def test_refund_revokes_matching_sale_only(mock_config):
    _ready(mock_config)
    mgr = MagicMock()
    mgr.revoke_gumroad_sale.return_value = True
    status, detail = handle_gumroad_ping(
        _sale(resource_name="refund"),
        ping_token="ping-secret",
        subscriber_manager=mgr,
    )
    assert (status, detail) == (200, "revoked")
    mgr.revoke_gumroad_sale.assert_called_once_with("sale_1")
    mgr.grant_gumroad_access.assert_not_called()

    mgr.revoke_gumroad_sale.return_value = False
    status, detail = handle_gumroad_ping(
        _sale(resource_name="refund", sale_id="old_sale"),
        ping_token="ping-secret",
        subscriber_manager=mgr,
    )
    assert (status, detail) == (200, "revoke_noop")


@patch("routes.billing_routes.handle_gumroad_ping", return_value=(200, "activated"))
def test_ping_route_reads_form_and_token(mock_handle):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(billing_bp)
    client = app.test_client()
    res = client.post(
        "/api/billing/gumroad/ping?token=ping-secret",
        data={"email": "reader@example.com", "seller_id": "seller_1"},
    )
    assert res.status_code == 200
    assert res.get_json()["detail"] == "activated"
    args, kwargs = mock_handle.call_args
    assert args[0]["email"] == "reader@example.com"
    assert kwargs["ping_token"] == "ping-secret"


def test_checkout_partial_links_region_product():
    app = Flask(__name__, template_folder=str(_TEMPLATES))
    app.config["TESTING"] = True
    with app.app_context():
        html = render_template(
            "partials/ai_summary_checkout_form.html",
            checkout_locale="en",
            checkout_default_region="us",
            GUMROAD_URL_US="https://gumroad.com/l/us-summary",
            GUMROAD_URL_JP="https://gumroad.com/l/jp-summary",
            GUMROAD_ACCESS_DAYS=30,
            ENABLE_AI_SUMMARY_CHECKOUT=False,
        )
        ja = render_template(
            "partials/ai_summary_checkout_form.html",
            checkout_locale="ja",
            checkout_default_region="jp",
            GUMROAD_URL_US="https://gumroad.com/l/us-summary",
            GUMROAD_URL_JP="https://gumroad.com/l/jp-summary",
            GUMROAD_ACCESS_DAYS=30,
            ENABLE_AI_SUMMARY_CHECKOUT=False,
        )
    assert 'href="https://gumroad.com/l/us-summary"' in html
    assert "Get the email" in html
    assert "next morning" in html
    assert "$2 for about 30 days" in html
    assert "No auto-renew" in html
    assert "a month" not in html
    assert "お試し購入" not in html
    assert 'data-checkout-enabled="false"' in html
    assert "¥300で約30日" in ja
    assert "自動更新はありません" in ja
    assert "月額" not in ja
