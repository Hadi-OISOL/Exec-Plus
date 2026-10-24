"""Use case: Proves scheduled reports reach a real SMTP server over STARTTLS with AUTH LOGIN.

What it does: Runs a loopback aiosmtpd server with a test-only CA, requires STARTTLS and
authentication, drives the scheduler that `manage deliver-reports` calls, checks the received
headers/body, the transient-failure retry and that certificate/password checks stay strict.
"""

import asyncio
import datetime as dt
import smtplib
import socket
import ssl
from email import message_from_bytes
from ipaddress import IPv4Address
from uuid import uuid4

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from execplus.bootstrap import build_runtime
from execplus.config import Settings
from execplus.infrastructure.email import SMTPEmailDelivery
from test_phase3_integration import analysis, setup
from test_report_email_delivery import schedule

USERNAME, PASSWORD, SENDER = "reports", "fictional-smtp-password", "reports@example.test"


def _certificates(folder):
    now = dt.datetime.now(dt.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ExecPlus test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(IPv4Address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    ca_file, cert_file, key_file = folder / "ca.pem", folder / "cert.pem", folder / "key.pem"
    ca_file.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_file.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return ca_file, cert_file, key_file


class Mailbox:
    def __init__(self):
        self.messages, self.sessions, self.logins = [], [], []
        self.temporary_failures = 0

    def authenticate(self, server, session, envelope, mechanism, auth_data):
        valid = isinstance(auth_data, LoginPassword) and (
            auth_data.login,
            auth_data.password,
        ) == (USERNAME.encode(), PASSWORD.encode())
        self.logins.append((mechanism, valid, session.ssl is not None))
        return AuthResult(success=valid, handled=False)

    async def handle_DATA(self, server, session, envelope):
        if self.temporary_failures:
            self.temporary_failures -= 1
            return "451 4.3.0 Try again later"
        self.sessions.append(
            dict(
                tls=session.ssl is not None,
                authenticated=session.authenticated,
                mail_from=envelope.mail_from,
                rcpt_tos=list(envelope.rcpt_tos),
            )
        )
        self.messages.append(message_from_bytes(envelope.original_content))
        return "250 2.0.0 Queued"


@pytest.fixture
def smtp_server(tmp_path):
    ca_file, cert_file, key_file = _certificates(tmp_path)
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(cert_file, key_file)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    mailbox = Mailbox()
    controller = Controller(
        mailbox,
        hostname="127.0.0.1",
        port=port,
        tls_context=context,
        require_starttls=True,
        auth_required=True,
        auth_require_tls=True,
        auth_exclude_mechanism=["PLAIN"],
        authenticator=mailbox.authenticate,
    )
    controller.start()
    yield mailbox, port, str(ca_file)
    controller.stop()


def _delivery(port, ca_file, **overrides):
    values = dict(
        _env_file=None,
        environment="test",
        email_mode="smtp",
        smtp_host="127.0.0.1",
        smtp_port=port,
        smtp_username=USERNAME,
        smtp_password=PASSWORD,
        smtp_sender=SENDER,
        smtp_security="starttls",
        smtp_ca_file=ca_file,
    )
    runtime = build_runtime(Settings(**(values | overrides)))
    try:
        email = runtime.reports.email
        assert isinstance(email, SMTPEmailDelivery)
        return email
    finally:
        runtime.engine.dispose()


def test_scheduled_report_is_delivered_over_starttls_with_auth_login(integration, smtp_server):
    mailbox, port, ca_file = smtp_server
    env = integration
    owner, actor, wid, _did, _uid, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.runtime.reports.email = _delivery(port, ca_file)
    schedule(env, owner, wid, saved)
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=25)
    assert asyncio.run(env.runtime.reports.deliver_due(now)) == dict(
        sent=1, failed=0, unauthorized=0, cancelled=0
    )
    assert asyncio.run(env.runtime.reports.deliver_due(now))["sent"] == 0
    assert mailbox.logins == [("LOGIN", True, True)]
    assert mailbox.sessions == [
        dict(tls=True, authenticated=True, mail_from=SENDER, rcpt_tos=[actor.email])
    ]
    message = mailbox.messages[0]
    assert message["From"] == SENDER and message["To"] == actor.email
    assert message["Subject"] == "Syntelio saved analysis report"
    assert message["Message-ID"].endswith("@execplus.report>")
    body = message.get_payload(decode=True).decode().replace("\r\n", "\n")
    assert body.startswith("Saved analysis (original revision)\n")
    assert "0.300000000000" in body and "Evidence: " in body
    assert f"/workspace?workspace={wid}&saved={saved['id']}" in body
    assert "Manage or unsubscribe: " in body


def test_temporary_smtp_rejection_is_retried_and_delivered_exactly_once(integration, smtp_server):
    mailbox, port, ca_file = smtp_server
    env = integration
    owner, _actor, wid, _did, _uid, root = setup(env)
    saved, _ = analysis(env, owner, root)
    env.runtime.reports.email = _delivery(port, ca_file)
    schedule(env, owner, wid, saved)
    first = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=25)
    mailbox.temporary_failures = 1
    assert asyncio.run(env.runtime.reports.deliver_due(first))["failed"] == 1
    assert mailbox.messages == [] and mailbox.temporary_failures == 0
    later = first + dt.timedelta(minutes=10)
    assert asyncio.run(env.runtime.reports.deliver_due(later))["sent"] == 0
    retry = first + dt.timedelta(minutes=16)
    assert asyncio.run(env.runtime.reports.deliver_due(retry))["sent"] == 1
    assert asyncio.run(env.runtime.reports.deliver_due(first + dt.timedelta(hours=2)))["sent"] == 0
    assert len(mailbox.messages) == 1
    assert [login[1:] for login in mailbox.logins] == [(True, True), (True, True)]


def test_untrusted_certificate_and_wrong_password_are_refused(smtp_server):
    mailbox, port, ca_file = smtp_server
    with pytest.raises(ssl.SSLCertVerificationError):
        _delivery(port, "").send("a@example.test", "s", "b", uuid4())
    with pytest.raises(ssl.SSLCertVerificationError):
        _delivery(port, ca_file, smtp_host="localhost").send("a@example.test", "s", "b", uuid4())
    with pytest.raises(smtplib.SMTPAuthenticationError):
        _delivery(port, ca_file, smtp_password="wrong").send("a@example.test", "s", "b", uuid4())
    assert mailbox.messages == []
    assert mailbox.logins == [("LOGIN", False, True)]
