from __future__ import annotations

import asyncio

from app.services.auth_notification_delivery import AuthEmailMessage
from app.services.smtp_auth_email_sender import SmtpAuthEmailSender


class FakeSmtp:
    instance = None

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.logged_in = None
        self.message = None
        FakeSmtp.instance = self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.message = message


def test_smtp_sender_uses_tls_authenticated_connection(monkeypatch) -> None:
    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSmtp)
    sender = SmtpAuthEmailSender(
        host="smtp.example.test", port=465, username="mailer", password="secret",
        from_address="no-reply@example.test",
    )
    asyncio.run(sender.send(AuthEmailMessage(
        recipient="customer@example.test",
        subject="验证邮箱",
        body="请验证邮箱",
        action_url="https://app.example.test/verify-email?token=secret",
    )))

    smtp = FakeSmtp.instance
    assert smtp.logged_in == ("mailer", "secret")
    assert smtp.message["To"] == "customer@example.test"
    assert smtp.message["From"] == "no-reply@example.test"
