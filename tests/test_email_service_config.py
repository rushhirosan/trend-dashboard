"""Tests for EmailService SendGrid / SMTP configuration."""

from utils.email_service import EmailService


def test_email_provider_smtp_ignores_sendgrid_key(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.setenv("SMTP_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("SENDER_PASSWORD", "app-password-here")
    monkeypatch.delenv("SENDGRID_FROM_EMAIL", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    svc = EmailService()
    assert svc.email_provider == "smtp"
    assert not svc.sendgrid_api_key
    assert svc.smtp_server == "smtp.gmail.com"
    assert svc.smtp_user == "me@gmail.com"
    assert svc.from_email == "me@gmail.com"
    assert svc.is_configured()


def test_email_service_auto_prefers_gmail_when_configured(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "auto")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.setenv("SMTP_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    monkeypatch.setenv("SENDER_PASSWORD", "app-password-here")
    monkeypatch.delenv("SENDGRID_FROM_EMAIL", raising=False)
    svc = EmailService()
    assert svc.email_provider == "smtp"
    assert svc.smtp_server == "smtp.gmail.com"


def test_email_service_prefers_sendgrid(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "from@example.com")
    monkeypatch.delenv("SENDER_PASSWORD", raising=False)
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    svc = EmailService()
    assert svc.email_provider == "sendgrid"
    assert svc.smtp_server == "smtp.sendgrid.net"
    assert svc.smtp_user == "apikey"
    assert svc.smtp_password == "SG.testkey"
    assert svc.from_email == "from@example.com"
    assert svc.is_configured()


def test_email_service_sendgrid_falls_back_from_sender_email(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.delenv("SENDGRID_FROM_EMAIL", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    monkeypatch.setenv("SENDER_EMAIL", "me@gmail.com")
    svc = EmailService()
    assert svc.from_email == "me@gmail.com"
    assert svc.is_configured()


def test_email_service_sendgrid_ignores_placeholder_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "from@example.com")
    monkeypatch.setenv("SMTP_SERVER", "smtp.example.com")
    svc = EmailService()
    assert svc.smtp_server == "smtp.sendgrid.net"


def test_email_service_not_configured_without_from(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.testkey")
    for k in ("SENDGRID_FROM_EMAIL", "MAIL_FROM", "SENDER_EMAIL"):
        monkeypatch.delenv(k, raising=False)
    svc = EmailService()
    assert not svc.is_configured()
