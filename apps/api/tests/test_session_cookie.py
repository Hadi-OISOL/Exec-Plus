"""Use case: Proves browser sessions survive refresh through an HttpOnly cookie safely.

What it does: Covers cookie issue on password and Google sign-in, the request-header guard,
bearer precedence and logout revocation/clearing against isolated PostgreSQL.
"""

from test_google_access import enable, sign_in
from test_local_accounts_integration import login, register

COOKIE = "execplus_session"
GUARD = {"X-ExecPlus-Request": "1"}


def issued_cookie(response):
    header = next(
        value for value in response.headers.get_list("set-cookie") if value.startswith(COOKIE + "=")
    )
    assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
    assert "Secure" not in header and "Max-Age=28" in header
    return header


def test_login_sets_cookie_that_authenticates_only_with_the_request_header(integration):
    env = integration
    register(env)
    response = env.client.post(
        "/auth/login",
        json={"email": "native@example.test", "password": "fictional initial password 27"},
    )
    assert response.status_code == 200 and response.json()["token"]
    issued_cookie(response)
    assert env.client.cookies.get(COOKIE) == response.json()["token"]
    me = env.client.get("/auth/me", headers=GUARD)
    assert me.status_code == 200 and me.json()["email"] == "native@example.test"
    refused = env.client.get("/auth/me")
    assert refused.status_code == 401
    assert refused.json()["error"]["code"] == "session_header_required"


def test_bearer_takes_precedence_over_the_cookie(integration):
    env = integration
    register(env)
    headers, _ = login(env)
    env.client.cookies.set(COOKIE, "not-a-session-token-but-long-enough-000")
    assert env.client.get("/auth/me", headers=headers).status_code == 200
    assert env.client.get("/auth/me", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_logout_by_cookie_revokes_and_clears_even_when_already_invalid(integration):
    env = integration
    register(env)
    headers, body = login(env)
    logout = env.client.post("/auth/logout", headers=GUARD)
    assert logout.status_code == 204
    assert 'execplus_session=""' in logout.headers["set-cookie"]
    assert COOKIE not in env.client.cookies
    assert env.client.get("/auth/me", headers=headers).status_code == 401
    env.client.cookies.set(COOKIE, body["token"])
    again = env.client.post("/auth/logout", headers=GUARD)
    assert again.status_code == 204 and 'execplus_session=""' in again.headers["set-cookie"]


def test_logout_by_bearer_still_revokes(integration):
    env = integration
    register(env)
    headers, _ = login(env)
    env.client.cookies.clear()
    assert env.client.post("/auth/logout", headers=headers).status_code == 204
    assert env.client.get("/auth/me", headers=headers).status_code == 401


def test_google_session_exchange_sets_the_cookie(integration):
    env = integration
    google, _ = enable(env)
    sign_in(env, google, "cookie.person@example.test")
    response = env.client.post("/auth/oauth/exchange", json={})
    assert response.status_code == 200
    issued_cookie(response)
    assert env.client.cookies.get(COOKIE) == response.json()["token"]
    me = env.client.get("/auth/me", headers=GUARD)
    assert me.json()["email"] == "cookie.person@example.test"


def test_password_change_replaces_the_cookie_with_the_rotated_session(integration):
    env = integration
    register(env)
    _, body = login(env)
    response = env.client.post(
        "/auth/password",
        headers=GUARD,
        json={
            "current_password": "fictional initial password 27",
            "new_password": "fictional replacement password 49",
        },
    )
    assert response.status_code == 200, response.text
    issued_cookie(response)
    assert env.client.cookies.get(COOKIE) == response.json()["token"] != body["token"]
    assert env.client.get("/auth/me", headers=GUARD).status_code == 200


def test_cors_preflight_allows_the_request_header_with_credentials(integration):
    env = integration
    origin = env.client.app.state.web_origin
    preflight = env.client.options(
        "/auth/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-execplus-request",
        },
    )
    assert preflight.status_code == 200
    assert "x-execplus-request" in preflight.headers["access-control-allow-headers"].lower()
    assert preflight.headers["access-control-allow-credentials"] == "true"
