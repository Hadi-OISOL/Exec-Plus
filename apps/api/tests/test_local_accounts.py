"""Use case: Tests fixed-cost password handling and pre-parse account request bounds.

What it does: Exercises real hashing, credential validation, origins
and adversarial streamed bodies.
"""

import asyncio
import json

import pytest

from execplus.domain.accounts import password_input
from execplus.domain.ingestion import IngestionError
from execplus.infrastructure import passwords
from execplus.infrastructure.passwords import ScryptPasswords
from execplus.presentation.account_request_guard import AccountRequestGuard

PASSWORD = "a safe synthetic passphrase 27"


def test_real_scrypt_salts_and_constant_parameters():
    hasher = ScryptPasswords()
    first, second = hasher.hash(PASSWORD), hasher.hash(PASSWORD)
    assert first != second
    assert first.startswith("scrypt-v1$131072$8$1$")
    assert hasher.verify(PASSWORD, first)
    assert not hasher.verify("a different synthetic phrase", first)
    assert not hasher.verify(PASSWORD, None)
    assert not hasher.verify(PASSWORD, first.replace("131072", "2147483648"))
    assert not hasher.verify(PASSWORD, "invalid")


def test_hash_admission_fails_fast_without_queuing():
    assert passwords._HASH_SLOTS.acquire(blocking=False)
    assert passwords._HASH_SLOTS.acquire(blocking=False)
    try:
        with pytest.raises(IngestionError) as caught:
            ScryptPasswords().hash(PASSWORD)
        assert caught.value.status == 503
        assert caught.value.code == "authentication_busy"
    finally:
        passwords._HASH_SLOTS.release()
        passwords._HASH_SLOTS.release()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "short",
        "x" * 15,
        " " * 15,
        "x" * 129,
        "long enough\\0password",
        "surrogate-\\ud800-value",
    ],
)
def test_new_password_bounds(value):
    if "\\0" in value:
        value = value.replace("\\0", "\0")
    if "\\ud800" in value:
        value = value.replace("\\ud800", "\ud800")
    with pytest.raises(IngestionError):
        password_input(value, new=True)


def test_password_spaces_and_unicode_are_preserved():
    assert password_input("  a varied long password  ", new=True) == "  a varied long password  "
    assert password_input("یہ ایک لمبا محفوظ پاس ورڈ ہے", new=True)


def run_guard(chunks, *, headers=None, path="/auth/register", method="POST"):
    received, sent = [], []
    messages = [
        {"type": "http.request", "body": body, "more_body": i < len(chunks) - 1}
        for i, body in enumerate(chunks)
    ]

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        received.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    scope = {
        "type": "http",
        "path": path,
        "method": method,
        "headers": headers if headers is not None else [(b"content-type", b"application/json")],
    }
    asyncio.run(AccountRequestGuard(app, "http://localhost:3000")(scope, receive, send))
    status = next(message["status"] for message in sent if message["type"] == "http.response.start")
    return status, received, sent


@pytest.mark.parametrize("declared", [None, b"1", b"8192"])
def test_streamed_body_limit_does_not_trust_content_length(declared):
    headers = [(b"content-type", b"application/json")]
    if declared is not None:
        headers.append((b"content-length", declared))
    status, received, sent = run_guard([b"x" * 4096, b"y" * 4097], headers=headers)
    assert status == 413 and not received
    assert b"x" * 30 not in repr(sent).encode()


def test_allowed_body_is_replayed_exactly_once_to_parser():
    status, received, _ = run_guard([b'{"email":', b'"demo@example.test"}'])
    assert status == 200
    assert received == [
        {"type": "http.request", "body": b'{"email":"demo@example.test"}', "more_body": False}
    ]


@pytest.mark.parametrize(
    "headers,status",
    [
        ([(b"content-type", b"text/plain")], 415),
        ([(b"content-type", b"application/json"), (b"origin", b"https://other.test")], 403),
        ([(b"content-type", b"application/json"), (b"origin", b"null")], 403),
        (
            [
                (b"content-type", b"application/json"),
                (b"origin", b"https://other.test"),
                (b"origin", b"http://localhost:3000"),
            ],
            403,
        ),
        (
            [(b"content-type", b"application/json"), (b"content-length", b"99999999999999999999")],
            413,
        ),
        ([(b"content-type", b"application/json"), (b"content-length", b"-1")], 413),
    ],
)
def test_foreign_origins_duplicate_origins_and_bad_body_headers_are_rejected(headers, status):
    actual, received, sent = run_guard(
        [json.dumps({"password": PASSWORD}).encode()], headers=headers
    )
    assert actual == status and not received
    assert PASSWORD not in repr(sent)


@pytest.mark.parametrize(
    "path",
    [
        "/auth/login",
        "/auth/password",
        "/auth/disable",
        "/workspaces/a/onboarding-progress",
        "/workspaces/a/invitations/b/identity-approval",
    ],
)
def test_every_new_mutation_has_the_stream_guard(path):
    status, received, _ = run_guard(
        [b"x" * 8193], path=path, method="PUT" if "progress" in path else "POST"
    )
    assert status == 413 and not received


def test_unrelated_file_uploads_keep_their_existing_stream_policy():
    status, received, _ = run_guard(
        [b"x" * 8193],
        path="/workspaces/a/datasets/b/uploads",
        headers=[(b"content-type", b"text/csv")],
    )
    assert status == 200 and received


@pytest.mark.parametrize(
    "path",
    [
        "/admin/incidents/thresholds/ingestion",
        "/admin/workspaces/synthetic/plan",
        "/admin/plans/demo",
    ],
)
@pytest.mark.parametrize("declared", [None, b"1"])
def test_local_administrative_mutations_share_stream_and_origin_guards(path, declared):
    headers = [(b"content-type", b"application/json")]
    if declared is not None:
        headers.append((b"content-length", declared))
    status, received, _ = run_guard(
        [b"x" * 4000, b"x" * 4193], headers=headers, path=path, method="PUT"
    )
    assert status == 413 and not received
    status, received, _ = run_guard(
        [b"{}"],
        headers=[*headers, (b"origin", b"https://untrusted.example")],
        path=path,
        method="PUT",
    )
    assert status == 403 and not received


def test_recovery_cli_requires_interactive_identity_check_before_reading_password(
    monkeypatch, capsys
):
    from types import SimpleNamespace
    from uuid import uuid4

    from execplus import manage

    def forbidden(*args, **kwargs):
        raise AssertionError("No password or runtime access should occur")

    monkeypatch.setattr(manage.getpass, "getpass", forbidden)
    monkeypatch.setattr(manage, "build_runtime", forbidden)
    monkeypatch.setattr(manage.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        manage._recover_account(
            SimpleNamespace(account_id=uuid4(), identity_checked=True, reenable=False)
        )
    assert "interactive operator" in capsys.readouterr().err


def test_recovery_cli_reads_password_privately_and_prints_no_credential(monkeypatch, capsys):
    from types import SimpleNamespace
    from uuid import uuid4

    from execplus import manage

    identifier, captured = uuid4(), []
    runtime = SimpleNamespace(
        accounts=SimpleNamespace(recover=lambda *args, **kwargs: captured.append((args, kwargs))),
        engine=SimpleNamespace(dispose=lambda: None),
    )
    monkeypatch.setattr(manage.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(manage.getpass, "getpass", lambda prompt: PASSWORD)
    monkeypatch.setattr(manage, "Settings", lambda: None)
    monkeypatch.setattr(manage, "build_runtime", lambda settings: runtime)
    manage._recover_account(
        SimpleNamespace(account_id=identifier, identity_checked=True, reenable=True)
    )
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    assert json.loads(output.out)["account_id"] == str(identifier)
    assert captured == [((identifier, PASSWORD), {"identity_checked": True, "reenable": True})]


def test_recovery_cli_refuses_a_terminal_that_cannot_hide_passwords(monkeypatch, capsys):
    import warnings
    from types import SimpleNamespace
    from uuid import uuid4

    from execplus import manage

    def unavailable(prompt):
        warnings.warn(
            "Synthetic terminal cannot hide input", manage.getpass.GetPassWarning, stacklevel=2
        )
        raise AssertionError("An echoing fallback must never read a password")

    def forbidden(*args, **kwargs):
        raise AssertionError("No runtime access should occur")

    monkeypatch.setattr(manage.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(manage.getpass, "getpass", unavailable)
    monkeypatch.setattr(manage, "build_runtime", forbidden)
    with pytest.raises(SystemExit):
        manage._recover_account(
            SimpleNamespace(account_id=uuid4(), identity_checked=True, reenable=False)
        )
    assert "account_recovery_failure" in capsys.readouterr().err
