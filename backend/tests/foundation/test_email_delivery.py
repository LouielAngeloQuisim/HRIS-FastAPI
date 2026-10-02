"""Validate the upgraded email library without contacting an SMTP server."""

from unittest.mock import patch

from emails.message import Message

from app.config.settings import settings
from app.utils import send_email


def test_send_email_preserves_sender_and_delivery_options(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", None)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", None)
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "sender@example.com")
    monkeypatch.setattr(settings, "EMAILS_FROM_NAME", "HRIS")
    with patch.object(Message, "send", autospec=True, return_value=None) as send:
        send_email(
            email_to="recipient@example.com", subject="Test", html_content="<p>Test</p>"
        )
        message = send.call_args.args[0]
        assert message.mail_from == ("HRIS", "sender@example.com")
        assert message.subject == "Test"
        assert send.call_args.kwargs == {
            "to": "recipient@example.com",
            "smtp": {"host": "smtp.example.com", "port": 587, "tls": True},
        }
