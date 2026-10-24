"""Use case: Delivers explicitly configured reports without exposing mail content in logs.

What it does: Defaults to disabled delivery and supports authenticated SMTP over implicit TLS
or STARTTLS, optionally trusting an extra CA bundle while keeping
verification on; unencrypted delivery is limited to local/test fake servers by configuration.
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Literal
from uuid import UUID

from execplus.domain.errors import ProviderUnavailableError


class DisabledEmailDelivery:
    def send(self, recipient: str, subject: str, body: str, delivery_id: UUID) -> None:
        raise ProviderUnavailableError("Email delivery is not configured")


class SMTPEmailDelivery:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        security: Literal["ssl", "starttls", "none"] = "ssl",
        ca_file: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender
        self.security = security
        self.ca_file = ca_file

    def send(self, recipient: str, subject: str, body: str, delivery_id: UUID) -> None:
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = recipient
        message["Subject"] = subject
        message["Message-ID"] = f"<{delivery_id}@execplus.report>"
        message.set_content(body)
        context = ssl.create_default_context(cafile=self.ca_file or None)
        client = (
            smtplib.SMTP_SSL(self.host, self.port, timeout=10, context=context)
            if self.security == "ssl"
            else smtplib.SMTP(self.host, self.port, timeout=10)
        )
        with client:
            if self.security == "starttls":
                client.starttls(context=context)
            if self.username:
                client.login(self.username, self.password)
            client.send_message(message)
