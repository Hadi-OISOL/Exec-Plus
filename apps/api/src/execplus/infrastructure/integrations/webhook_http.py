"""Use case: Delivers fixed webhook bodies to operator-approved pinned destinations.

What it does: Avoids runtime DNS and redirects, verifies TLS hostnames, ignores proxy
configuration and interrupts socket work at a finite wall-clock deadline.
"""

import http.client
import ipaddress
import socket
import ssl
import threading
import time
from contextlib import suppress
from urllib.parse import urlsplit

from execplus.domain.ingestion import IngestionError
from execplus.domain.integration_access import origin
from execplus.domain.webhooks import destination


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, secure: bool, deadline: float) -> None:
        super().__init__(host, port, timeout=min(3, max(0.1, deadline - time.monotonic())))
        self.address, self.secure, self.deadline = address, secure, deadline

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), timeout=self.timeout)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.close()
            raise TimeoutError("Webhook connection deadline exhausted")
        self.sock.settimeout(remaining)
        if self.secure:
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(
                self.sock, server_hostname=self.host, do_handshake_on_connect=False
            )
            self.sock.do_handshake()

    def interrupt(self) -> None:
        current = self.sock
        if current is not None:
            with suppress(OSError):
                current.shutdown(socket.SHUT_RDWR)
            self.close()


class PinnedWebhookTransport:
    def __init__(
        self, destinations: dict[str, str], *, allow_local: bool = False, timeout_seconds: float = 5
    ) -> None:
        if not 0.1 <= timeout_seconds <= 10:
            raise ValueError("Webhook transport timeout must be bounded")
        self.destinations: dict[str, str] = {}
        self.allow_local, self.timeout_seconds = allow_local, timeout_seconds
        for name, address in destinations.items():
            normalized = origin(name, allow_local=allow_local)
            parsed = ipaddress.ip_address(address)
            if not parsed.is_global and not (allow_local and parsed.is_loopback):
                raise ValueError(
                    "Webhook targets need a public pinned IP or explicit local loopback"
                )
            if normalized in self.destinations:
                raise ValueError("Duplicate webhook destination origin")
            self.destinations[normalized] = str(parsed)

    def send(self, target: str, body: bytes, headers: dict[str, str]) -> int | None:
        normalized = destination(target, tuple(self.destinations), allow_local=self.allow_local)
        if len(body) > 4096 or set(headers) != {"X-ExecPlus-Signature", "X-ExecPlus-Event-ID"}:
            raise IngestionError(
                "webhook_body", "Webhook delivery exceeds its fixed contract.", 422
            )
        if any(len(value) > 200 or "\r" in value or "\n" in value for value in headers.values()):
            raise IngestionError("webhook_headers", "Invalid webhook signature metadata.", 422)
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
        base = origin(parsed.scheme + "://" + parsed.netloc, allow_local=self.allow_local)
        deadline = time.monotonic() + self.timeout_seconds
        connection = PinnedConnection(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            self.destinations[base],
            parsed.scheme == "https",
            deadline,
        )
        timer = threading.Timer(self.timeout_seconds, connection.interrupt)
        timer.daemon = True
        timer.start()
        try:
            connection.request(
                "POST",
                parsed.path or "/",
                body,
                {
                    **headers,
                    "Content-Type": "application/json",
                    "User-Agent": "ExecPlus-Webhook/1",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            status = response.status
            response.read(4097)
            return status if time.monotonic() <= deadline else None
        except (OSError, http.client.HTTPException):
            return None
        finally:
            timer.cancel()
            connection.close()
