"""Waitlist API のユニットテスト"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from routes.waitlist_routes import waitlist_bp


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(waitlist_bp)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@patch("routes.waitlist_routes._get_manager")
def test_ai_summary_waitlist_success(mock_get_manager, client):
    mgr = MagicMock()
    mgr.add.return_value = (True, "登録を受け付けました。")
    mock_get_manager.return_value = mgr

    res = client.post(
        "/api/waitlist/ai-summary",
        json={"email": "test@example.com", "region": "jp", "source": "fake_door_modal"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    mgr.add.assert_called_once_with("test@example.com", "jp", "fake_door_modal")


@patch("routes.waitlist_routes._get_manager")
def test_ai_summary_waitlist_validation_error(mock_get_manager, client):
    mgr = MagicMock()
    mgr.add.return_value = (False, "有効なメールアドレスを入力してください")
    mock_get_manager.return_value = mgr

    res = client.post(
        "/api/waitlist/ai-summary",
        json={"email": "not-an-email", "region": "jp"},
    )
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
