"""Use case: Proves the October 22 session, header and rate-limit keying hardening.

What it does: Checks response security headers, Secure cookies outside local/test,
fixation-safe sign-in and trusted-proxy client keying without real network access.
"""

from types import SimpleNamespace

from starlette.requests import Request

from execplus.config import Settings
from execplus.presentation.routes.accounts import peer
from test_local_accounts_integration import PASSWORD, login, register

COOKIE = "execplus_session"
GUARD = {"X-ExecPlus-Request": "1"}


def test_api_responses_carry_security_headers_including_errors(integration):
    env = integration
    for response in (
        env.client.get("/health/live"),
        env.client.get("/auth/me"),
        env.client.post("/auth/login", content=b"x", headers={"content-type": "text/plain"}),
    ):
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert "Strict-Transport-Security" not in response.headers


def test_secure_cookie_and_hsts_when_deployment_requires_https(integration):
    env = integration
    register(env)
    env.client.app.state.secure_cookies = True
    try:
        response = env.client.post(
            "/auth/login", json={"email": "native@example.test", "password": PASSWORD}
        )
        assert response.status_code == 200
        header = next(
            value
            for value in response.headers.get_list("set-cookie")
            if value.startswith(COOKIE + "=")
        )
        assert "Secure" in header and "HttpOnly" in header
        assert response.headers["Strict-Transport-Security"].startswith("max-age=")
    finally:
        env.client.app.state.secure_cookies = False


def test_settings_default_secure_cookies_only_outside_local_and_test():
    from execplus.main import create_app

    assert create_app(Settings(_env_file=None, environment="test")).state.secure_cookies is False
    assert (
        create_app(Settings(_env_file=None, environment="production")).state.secure_cookies
        is True
    )
    assert (
        create_app(
            Settings(_env_file=None, environment="production", session_cookie_secure=False)
        ).state.secure_cookies
        is False
    )


def test_sign_in_revokes_the_session_cookie_the_browser_already_held(integration):
    env = integration
    register(env)
    first_headers, first = login(env)
    assert env.client.cookies.get(COOKIE) == first["token"]
    second = env.client.post(
        "/auth/login", json={"email": "native@example.test", "password": PASSWORD}
    ).json()
    assert env.client.cookies.get(COOKIE) == second["token"]
    assert env.client.get("/auth/me", headers=first_headers).status_code == 401
    assert env.client.get("/auth/me", headers=GUARD).status_code == 200


def request_from(host, forwarded=None, trusted=()):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    app = SimpleNamespace(state=SimpleNamespace(trusted_proxies=frozenset(trusted)))
    return Request(
        {"type": "http", "headers": headers, "client": (host, 1), "app": app, "method": "GET"}
    )


def test_rate_limit_peer_uses_forwarded_address_only_from_trusted_proxies():
    assert peer(request_from("10.0.0.5", "198.51.100.7")) == "10.0.0.5"
    assert peer(request_from("10.0.0.5", "203.0.113.9, 198.51.100.7", ["10.0.0.5"])) == (
        "198.51.100.7"
    )
    assert peer(request_from("10.0.0.5", None, ["10.0.0.5"])) == "10.0.0.5"
    assert peer(request_from("127.0.0.1", "198.51.100.7", ["10.0.0.5"])) == "127.0.0.1"
