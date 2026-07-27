"""Tests for EmailService Resend / SMTP configuration."""

from utils.email_service import EmailService


def test_email_provider_smtp_ignores_resend_key(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "noreply@trends-dashboard.com")
    monkeypatch.setenv("SMTP_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("SENDER_PASSWORD", "app-password-here")
    monkeypatch.delenv("MAIL_FROM", raising=False)
    svc = EmailService()
    assert svc.email_provider == "smtp"
    assert not svc.resend_api_key
    assert svc.smtp_server == "smtp.gmail.com"
    assert svc.smtp_user == "me@gmail.com"
    # dogfood SMTP では RESEND_FROM を使わない
    assert svc.from_email == "me@gmail.com"
    assert svc.is_configured()


def test_email_service_auto_prefers_resend_when_configured(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "auto")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "noreply@trends-dashboard.com")
    monkeypatch.setenv("SMTP_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("SENDER_PASSWORD", "app-password-here")
    svc = EmailService()
    assert svc.email_provider == "resend"
    assert svc.from_email == "noreply@trends-dashboard.com"


def test_email_service_prefers_resend(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "from@example.com")
    monkeypatch.delenv("SENDER_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    svc = EmailService()
    assert svc.email_provider == "resend"
    assert svc.resend_api_key == "re_testkey"
    assert svc.from_email == "from@example.com"
    assert svc.is_configured()


def test_email_service_resend_falls_back_from_sender_email(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    svc = EmailService()
    assert svc.from_email == "me@gmail.com"
    assert svc.is_configured()


def test_email_service_resend_ignores_placeholder_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "from@example.com")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    svc = EmailService()
    assert svc.email_provider == "resend"
    assert not svc.smtp_server


def test_email_service_auto_uses_resend_without_gmail(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "auto")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "from@example.com")
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    monkeypatch.delenv("SENDER_PASSWORD", raising=False)
    monkeypatch.delenv("SENDER_EMAIL", raising=False)
    svc = EmailService()
    assert svc.email_provider == "resend"
    assert svc.is_configured()


def test_email_service_not_configured_without_from(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", "re_testkey")
    for k in ("RESEND_FROM_EMAIL", "MAIL_FROM", "SENDER_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    svc = EmailService()
    assert not svc.is_configured()
