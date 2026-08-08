"""SMTP SSL adapter for authentication emails."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from app.services.auth_notification_delivery import AuthEmailMessage


class SmtpAuthEmailSender:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        timeout_seconds: float = 15,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.timeout_seconds = timeout_seconds

    async def send(self, message: AuthEmailMessage) -> None:
        email = EmailMessage()
        email["From"] = self.from_address
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.body)
        await asyncio.to_thread(self._send_sync, email)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds) as smtp:
            smtp.login(self.username, self.password)
            smtp.send_message(message)
