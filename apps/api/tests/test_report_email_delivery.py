"""Use case: Proves scheduled reports travel over real SMTP to a local fake mail server.

What it does: Runs a loopback SMTP listener, delivers a due report through the configured
adapter, and covers transient-failure retry, duplicate slots and unencrypted-mode limits.
"""

import asyncio
import socketserver
import threading
from datetime import datetime, timedelta, timezone
from email import message_from_bytes

import pytest
from pydantic import ValidationError

from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.email import SMTPEmailDelivery
from test_phase3_integration import analysis, setup


class FakeSMTP(socketserver.StreamRequestHandler):
    def reply(self, line):
        self.wfile.write(line.encode() + b"\r\n")

    def handle(self):
        server = self.server
        self.reply("220 fake.test ESMTP")
        while line := self.rfile.readline():
            command = line.decode().strip().upper()
            if command.startswith("EHLO"):
                self.reply("250-fake.test")
                self.reply("250 AUTH PLAIN")
            elif command.startswith("AUTH"):
                server.auth.append(command)
                self.reply("235 accepted")
            elif command.startswith(("MAIL", "RCPT", "RSET", "NOOP")):
                if command.startswith("RCPT"):
                    server.recipients.append(line.decode().strip())
                self.reply("250 ok")
            elif command == "DATA":
                if server.fail_data:
                    self.reply("451 temporary failure")
                    continue
                self.reply("354 go ahead")
                data = bytearray()
                while (chunk := self.rfile.readline()) != b".\r\n":
                    data.extend(chunk[1:] if chunk.startswith(b"..") else chunk)
                server.messages.append(message_from_bytes(bytes(data)))
                self.reply("250 queued")
            elif command == "QUIT":
                self.reply("221 bye")
                return
            else:
                self.reply("502 unsupported")


@pytest.fixture
def mailbox():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeSMTP)
    server.daemon_threads = True
    server.messages, server.recipients, server.auth, server.fail_data = [], [], [], False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def schedule(env, owner, wid, saved):
    response = env.client.post(
        f"/workspaces/{wid}/report-schedules",
        headers=owner,
        json={"item_id": saved["id"], "interval_hours": 24},
    )
    assert response.status_code == 201, response.text


def test_due_report_is_delivered_once_over_smtp_with_exact_values(integration, mailbox):
    env = integration
    owner, actor, wid, _did, _uid, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.runtime.reports.email = SMTPEmailDelivery(
        "127.0.0.1",
        mailbox.server_address[1],
        "reports",
        "fictional-password",
        "reports@example.test",
        "none",
    )
    schedule(env, owner, wid, saved)
    now = datetime.now(timezone.utc) + timedelta(hours=25)
    assert asyncio.run(env.runtime.reports.deliver_due(now))["sent"] == 1
    assert asyncio.run(env.runtime.reports.deliver_due(now))["sent"] == 0
    assert len(mailbox.messages) == 1 and mailbox.auth
    message = mailbox.messages[0]
    assert message["To"] == actor.email and message["From"] == "reports@example.test"
    assert message["Message-ID"].endswith("@execplus.report>")
    body = message.get_payload(decode=True).decode()
    assert "0.300000000000" in body and "unsubscribe" in body


def test_transient_smtp_failure_retries_soon_instead_of_skipping_the_interval(
    integration, mailbox
):
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.runtime.reports.email = SMTPEmailDelivery(
        "127.0.0.1", mailbox.server_address[1], "", "", "reports@example.test", "none"
    )
    schedule(env, owner, wid, saved)
    first = datetime.now(timezone.utc) + timedelta(hours=25)
    mailbox.fail_data = True
    assert asyncio.run(env.runtime.reports.deliver_due(first))["failed"] == 1
    mailbox.fail_data = False
    assert asyncio.run(env.runtime.reports.deliver_due(first + timedelta(minutes=10)))[
        "sent"
    ] == 0
    assert asyncio.run(env.runtime.reports.deliver_due(first + timedelta(minutes=16)))[
        "sent"
    ] == 1
    assert len(mailbox.messages) == 1
    assert asyncio.run(env.runtime.reports.deliver_due(first + timedelta(hours=2)))["sent"] == 0


def test_unencrypted_smtp_is_limited_to_local_and_test_and_wired_from_settings(tmp_path):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            email_mode="smtp",
            smtp_host="mail.example.test",
            smtp_sender="reports@example.test",
            smtp_security="none",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            email_mode="smtp",
            smtp_host="mail.example.test",
            smtp_sender="reports@example.test",
        )
    runtime = build_runtime(
        Settings(
            _env_file=None,
            environment="test",
            email_mode="smtp",
            smtp_host="127.0.0.1",
            smtp_port=2525,
            smtp_sender="reports@example.test",
            smtp_security="none",
        )
    )
    try:
        email = runtime.reports.email
        assert isinstance(email, SMTPEmailDelivery) and email.security == "none"
    finally:
        runtime.engine.dispose()
