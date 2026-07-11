"""Tests for utils/alert_service.py"""

from unittest.mock import MagicMock, patch

from utils.alert_service import AlertService


def test_send_alert_skips_success_without_http(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    svc = AlertService()
    with patch("utils.alert_service.requests.post") as post:
        ok = svc.send_alert("success", "正常終了", "all good")
    assert ok is True
    post.assert_not_called()


def test_send_alert_sends_warning(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1/x")
    svc = AlertService()
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    with patch("utils.alert_service.requests.post", return_value=mock_resp) as post:
        ok = svc.send_alert("warning", "高失敗率", "something wrong")
    assert ok is True
    post.assert_called_once()
