"""Use case: Delivers explicitly configured reports without exposing mail content in logs.

What it does: Defaults to disabled delivery and supports authenticated SMTP over TLS.
"""

import smtplib
import ssl
from email.message import EmailMessage
from uuid import UUID

from execplus.domain.errors import ProviderUnavailableError


class DisabledEmailDelivery:
    def send(self, recipient: str, subject: str, body: str, delivery_id: UUID) -> None:
        raise ProviderUnavailableError("Email delivery is not configured")


class SMTPEmailDelivery:
    def __init__(self, host: str, port: int, username: str, password: str, sender: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender

    def send(self, recipient: str, subject: str, body: str, delivery_id: UUID) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = f"<{delivery_id}@execplus.report>"
        message.set_content(body)
        with smtplib.SMTP_SSL(
            self.host, self.port, timeout=10, context=ssl.create_default_context()
        ) as client:
            client.login(self.username, self.password)
            client.send_message(message)
