"""Use case: Verifies real bounded webhook delivery against a local receiver.

What it does: Checks exact signatures, pinned addressing, disabled destinations,
redirect refusal and a socket deadline without sending traffic outside loopback.
"""

import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.webhooks import WebhookEvent, signature, verify_signature
from execplus.infrastructure.integrations.webhook_http import PinnedWebhookTransport


@contextmanager
def receiver(status=204, delay=0):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append((self.path, dict(self.headers), body))
            if delay:
                time.sleep(delay)
            try:
                self.send_response(status)
                if status == 302:
                    self.send_header("Location", "http://127.0.0.1:1/never-follow")
                self.end_headers()
            except OSError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def event():
    value = WebhookEvent(
        uuid4(), uuid4(), "job.succeeded", uuid4(), uuid4(), datetime.now(timezone.utc)
    )
    body = value.body()
    secret = b"s" * 32
    stamp = int(time.time())
    return (
        body,
        secret,
        stamp,
        {
            "X-ExecPlus-Signature": signature(secret, stamp, body),
            "X-ExecPlus-Event-ID": str(value.id),
        },
    )


def test_actual_loopback_receiver_verifies_signed_bytes_and_only_fixed_headers(monkeypatch):
    body, secret, stamp, headers = event()
    with receiver() as (base, observed):
        transport = PinnedWebhookTransport({base: "127.0.0.1"}, allow_local=True)
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
        assert transport.send(base + "/events", body, headers) == 204
        assert len(observed) == 1
        path, received, data = observed[0]
        assert path == "/events" and data == body
        assert verify_signature(secret, received["X-ExecPlus-Signature"], data, stamp)
        assert received["X-ExecPlus-Event-ID"] == json.loads(body)["id"]
        assert "Authorization" not in received and "Cookie" not in received


def test_redirect_response_is_returned_without_following_it():
    body, _, _, headers = event()
    with receiver(status=302) as (base, observed):
        transport = PinnedWebhookTransport({base: "127.0.0.1"}, allow_local=True)
        assert transport.send(base + "/events", body, headers) == 302
        assert len(observed) == 1


def test_wall_deadline_interrupts_stalled_response():
    body, _, _, headers = event()
    with receiver(delay=2) as (base, observed):
        transport = PinnedWebhookTransport(
            {base: "127.0.0.1"}, allow_local=True, timeout_seconds=0.2
        )
        started = time.monotonic()
        assert transport.send(base + "/events", body, headers) is None
        assert time.monotonic() - started < 1
        assert len(observed) == 1


def test_disabled_or_private_targets_are_rejected_before_network():
    body, _, _, headers = event()
    with pytest.raises(IngestionError):
        PinnedWebhookTransport({}).send("https://external.test/events", body, headers)
    for address in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "::1", "0.0.0.0"):
        with pytest.raises(ValueError):
            PinnedWebhookTransport({"https://receiver.test": address})
    with pytest.raises(ValueError):
        PinnedWebhookTransport({"https://receiver.test": "10.0.0.1"}, allow_local=True)


def test_target_mismatch_and_extra_headers_do_not_reach_receiver():
    body, _, _, headers = event()
    with receiver() as (base, observed):
        transport = PinnedWebhookTransport({base: "127.0.0.1"}, allow_local=True)
        for target, supplied in [
            (base + "/events?secret=bad", headers),
            (base + "/events", {**headers, "Authorization": "bad"}),
        ]:
            with pytest.raises(IngestionError):
                transport.send(target, body, supplied)
        assert observed == []


def test_runtime_uses_canonical_approved_origin_without_revealing_signing_key():
    from execplus.bootstrap import build_runtime
    from execplus.config import Settings

    secret = "fictional-operator-secret-never-log-this-123"
    runtime = build_runtime(
        Settings(
            _env_file=None,
            environment="test",
            webhook_master_secret=secret,
            webhook_destinations={"HTTPS://Example.COM/": "93.184.216.34"},
        )
    )
    try:
        assert runtime.webhooks.allowed_origins == ("https://example.com",)
        assert runtime.webhooks.enabled
        assert secret not in repr(runtime)
    finally:
        runtime.engine.dispose()
