"""Run the durable authentication-email outbox worker."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import AsyncSessionLocal
from app.core.credential_encryption import require_stable_encryption_key
from app.core.runtime_environment import validate_runtime_environment
from app.services.auth_notification_delivery import deliver_pending_notifications
from app.services.smtp_auth_email_sender import SmtpAuthEmailSender


def _sender() -> SmtpAuthEmailSender:
    return SmtpAuthEmailSender(
        host=os.environ["SMTP_HOST"],
        port=int(os.getenv("SMTP_PORT", "465")),
        username=os.environ["SMTP_USERNAME"],
        password=os.environ["SMTP_PASSWORD"],
        from_address=os.environ["AUTH_EMAIL_FROM"],
    )


async def run() -> None:
    validate_runtime_environment()
    require_stable_encryption_key()
    sender = _sender()
    public_app_url = os.environ["PUBLIC_APP_URL"]
    while True:
        delivered = await deliver_pending_notifications(
            AsyncSessionLocal,
            sender,
            public_app_url=public_app_url,
        )
        await asyncio.sleep(1 if delivered else 5)


if __name__ == "__main__":
    asyncio.run(run())
