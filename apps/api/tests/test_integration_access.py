"""Use case: Verifies integration access and signed-event security contracts.

What it does: Exercises key separation, scope, expiry, single-use exchange, exact
origins, signature integrity and finite retry decisions with independent fixtures.
"""

import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from execplus.domain.ingestion import IngestionError
from execplus.domain.integration_access import (
    EMBED_MAX_SECONDS,
    EmbedGrant,
    IntegrationKey,
    issue_secret,
    lifetime,
    origin,
    secret_hash,
    validate_scope,
)
from execplus.domain.webhooks import (
    MAX_ATTEMPTS,
    WebhookEvent,
    destination,
    outcome,
    signature,
    signing_key,
    verify_signature,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_credentials_are_random_hashed_and_separated_from_other_token_kinds():
    pairs = [issue_secret(prefix) for prefix in ("epk", "epb", "eps")]
    assert len({token for token, _ in pairs}) == 3
    for token, digest in pairs:
        assert hashlib.sha256(token.encode()).hexdigest() == digest
        assert token not in digest and len(digest) == 64
        for prefix in ("epk", "epb", "eps"):
            if not token.startswith(prefix):
                with pytest.raises(IngestionError):
                    secret_hash(token, prefix)
    with pytest.raises(IngestionError):
        secret_hash("epk_" + "x" * 42, "epk")
    with pytest.raises(ValueError):
        issue_secret("session")


@pytest.mark.parametrize(
    "bad",
    [
        "https://*.example.test",
        "https://example.test/path",
        "https://example.test?x=1",
        "https://example.test#x",
        "https://user:secret@example.test",
        "null",
        "file:///x",
        "http://example.test",
        "https://example.test\n",
        "https://example.test:0",
        "https://example.test:65536",
        "https://%65xample.test",
        "https://example.test\\x",
        "http://127.0.0.1:9000",
        "https://localhost",
        "https://example.test https://other.test",
    ],
)
def test_host_origins_reject_wildcards_paths_credentials_and_unapproved_local_hosts(bad):
    with pytest.raises(IngestionError):
        origin(bad)


def test_origin_normalization_matches_exact_browser_origin_and_explicit_local_mode():
    assert origin("https://EXAMPLE.test:443/") == "https://example.test"
    assert origin("https://example.test:8443") == "https://example.test:8443"
    assert origin("http://localhost:3100", allow_local=True) == "http://localhost:3100"
    assert origin("http://[::1]:3100", allow_local=True) == "http://[::1]:3100"
    with pytest.raises(IngestionError):
        origin("http://internal.test:3100", allow_local=True)


@pytest.mark.parametrize("seconds", [0, -1, 901, True, 1.5])
def test_lifetime_refuses_invalid_or_unbounded_duration(seconds):
    with pytest.raises(IngestionError):
        lifetime(NOW, seconds, 900)


def test_explicit_scope_and_current_key_bounds():
    wid, did = uuid4(), uuid4()
    validate_scope((did,), ("rows:read", "query:read"))
    for datasets, operations in [
        ((), ("query:read",)),
        ((did, did), ("query:read",)),
        ((did,), ("query:write",)),
        ((did,), ("query:read",) * 2),
    ]:
        with pytest.raises(IngestionError):
            validate_scope(datasets, operations)
    key = IntegrationKey(
        uuid4(),
        wid,
        uuid4(),
        NOW,
        "Reader",
        "a" * 64,
        (did,),
        ("query:read",),
        NOW,
        NOW + timedelta(days=1),
    )
    key.authorize(NOW, wid, did, "query:read")
    for changed, when, workspace, dataset, operation in [
        (replace(key, revoked_at=NOW), NOW, wid, did, "query:read"),
        (key, key.expires_at, wid, did, "query:read"),
        (key, NOW, uuid4(), did, "query:read"),
        (key, NOW, wid, uuid4(), "query:read"),
        (key, NOW, wid, did, "rows:read"),
    ]:
        with pytest.raises(IngestionError):
            changed.authorize(when, workspace, dataset, operation)


def test_embed_exchange_is_single_use_and_rechecks_host_version_expiry_and_revocation():
    grant = EmbedGrant(
        uuid4(),
        uuid4(),
        uuid4(),
        NOW,
        uuid4(),
        2,
        "https://host.test",
        "b" * 64,
        NOW,
        NOW + timedelta(seconds=60),
    )
    _, digest = issue_secret("eps")
    for host, when in [("https://wrong.test", NOW), (grant.host_origin, grant.expires_at)]:
        with pytest.raises(IngestionError):
            grant.exchange(when, host, digest)
    session = grant.exchange(NOW, grant.host_origin, digest)
    assert session.session_expires_at == NOW + timedelta(seconds=EMBED_MAX_SECONDS)
    session.authorize(NOW, grant.host_origin, 2)
    with pytest.raises(IngestionError):
        session.exchange(NOW, grant.host_origin, digest)
    for value, host, version, when in [
        (session, "https://wrong.test", 2, NOW),
        (session, grant.host_origin, 3, NOW),
        (session, grant.host_origin, 2, session.session_expires_at),
        (replace(session, revoked_at=NOW), grant.host_origin, 2, NOW),
    ]:
        with pytest.raises(IngestionError):
            value.authorize(when, host, version)


def test_webhook_body_is_fixed_metadata_and_signature_matches_independent_hmac():
    event = WebhookEvent(uuid4(), uuid4(), "job.succeeded", uuid4(), uuid4(), NOW)
    body = event.body()
    assert set(json.loads(body)) == {
        "version",
        "id",
        "type",
        "resource_id",
        "dataset_id",
        "occurred_at",
    }
    assert body == event.body()
    secret = signing_key(b"m" * 32, event.subscription_id, 1)
    assert secret != signing_key(b"m" * 32, uuid4(), 1)
    assert secret != signing_key(b"m" * 32, event.subscription_id, 2)
    timestamp = int(NOW.timestamp())
    expected = hmac.new(secret, str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    header = signature(secret, timestamp, body)
    assert header == f"t={timestamp},v1={expected}"
    assert verify_signature(secret, header, body, timestamp)
    assert not verify_signature(secret, header, body + b" ", timestamp)
    assert not verify_signature(secret, header, body, timestamp + 301)
    assert not verify_signature(secret, header, body, timestamp - 301)
    assert not verify_signature(b"x" * 32, header, body, timestamp)
    assert not verify_signature(secret, "t=bad,v1=wrong", body, timestamp)
    with pytest.raises(ValueError):
        replace(event, kind="customer.private_message").body()


def test_webhook_destinations_require_exact_operator_allowlist_and_no_credentials():
    allowed = ("https://receiver.test",)
    assert destination("https://receiver.test/events", allowed) == "https://receiver.test/events"
    for value in [
        "https://receiver.test.evil/events",
        "https://receiver.test/events?token=x",
        "https://u:pw@receiver.test/events",
        "http://receiver.test/events",
        "https://receiver.test/events#x",
        "http://127.0.0.1:3101/events",
    ]:
        with pytest.raises(IngestionError):
            destination(value, allowed)
    assert (
        destination("http://127.0.0.1:3101/events", ("http://127.0.0.1:3101",), allow_local=True)
        == "http://127.0.0.1:3101/events"
    )


def test_finite_retry_keeps_success_terminal_and_never_follows_redirects():
    assert outcome(NOW, 1, 204) == ("delivered", NOW)
    assert outcome(NOW, 1, 302) == ("failed", NOW)
    assert outcome(NOW, 1, 401) == ("failed", NOW)
    for status in (None, 500, 503, 408, 429):
        assert outcome(NOW, 1, status) == ("pending", NOW + timedelta(seconds=10))
        assert outcome(NOW, MAX_ATTEMPTS, status) == ("failed", NOW)
    with pytest.raises(ValueError):
        outcome(NOW, MAX_ATTEMPTS + 1, 503)
