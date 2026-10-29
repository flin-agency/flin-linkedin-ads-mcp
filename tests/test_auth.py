from __future__ import annotations

from dataclasses import replace
import json
import socket
import stat
import time
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
import respx

from flin_linkedin_ads_mcp.auth import LinkedInAuth, TOKEN_URL
from flin_linkedin_ads_mcp.config import load_config
from flin_linkedin_ads_mcp.errors import LinkedInAuthError
from flin_linkedin_ads_mcp.linkedin_client import LinkedInClient


@pytest.fixture
def settings(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return load_config({
        "LINKEDIN_CLIENT_ID": "app-id", "LINKEDIN_CLIENT_SECRET": "app-secret",
        "LINKEDIN_REDIRECT_URI": f"http://127.0.0.1:{port}/callback",
        "LINKEDIN_TOKEN_FILE": str(tmp_path / "tokens.json"),
    })


@pytest.fixture
def auth(settings):
    manager = LinkedInAuth(settings)
    yield manager
    manager.close()


def saved_tokens(settings, **overrides):
    data = {"client_id": settings.client_id, "access_token": "old-token",
            "expires_at": time.time() + 3600, **overrides}
    settings.token_file.write_text(json.dumps(data))


def callback_path(auth, **params):
    login = auth.login()
    state = parse_qs(urlsplit(login["authorization_url"]).query)["state"][0]
    return "/callback?" + urlencode({"state": state, "code": "code-secret", **params})


def test_login_needs_setup_but_status_and_static_token_work(settings):
    manager = LinkedInAuth(replace(settings, client_id="", client_secret="", access_token="static"))
    assert manager.get_access_token() == "static"
    assert manager.status()["oauth_configured"] is False
    with pytest.raises(LinkedInAuthError, match="LINKEDIN_CLIENT_ID"):
        manager.login()


def test_missing_token_points_to_login(auth):
    with pytest.raises(LinkedInAuthError) as error:
        auth.get_access_token()
    assert error.value.details == {"next_tool": "linkedin_login"}


@respx.mock
def test_browser_callback_saves_private_tokens_and_reloads_without_restart(auth, settings):
    route = respx.post(TOKEN_URL).respond(200, json={
        "access_token": "access-secret", "expires_in": 3600,
        "refresh_token": "refresh-secret", "refresh_token_expires_in": 7200,
    })
    login = auth.login()
    query = parse_qs(urlsplit(login["authorization_url"]).query)
    assert query["scope"] == ["r_ads r_ads_reporting"]
    assert query["redirect_uri"] == [settings.redirect_uri]
    assert "app-secret" not in login["authorization_url"]
    assert auth.login()["authorization_url"] == login["authorization_url"]
    assert auth.status()["status"] == "awaiting_login"

    url = settings.redirect_uri + "?" + urlencode({"state": query["state"][0], "code": "code-secret"})
    respx.get(url).pass_through()
    response = httpx.get(url, trust_env=False)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert auth.get_access_token() == "access-secret"
    assert LinkedInAuth(settings).get_access_token() == "access-secret"
    assert stat.S_IMODE(settings.token_file.stat().st_mode) == 0o600
    body = parse_qs(route.calls[0].request.content.decode())
    assert body["client_secret"] == ["app-secret"]
    assert body["code"] == ["code-secret"]
    exposed = response.text + json.dumps(auth.status())
    for secret in ("access-secret", "refresh-secret", "app-secret", "code-secret"):
        assert secret not in exposed
    assert auth.status()["refresh_available"] is True


@respx.mock
def test_state_mismatch_does_not_exchange_or_consume_login(auth):
    path = callback_path(auth)
    pending = auth._pending
    assert auth._callback("/callback?state=wrong&code=bad", pending)[0] == 400
    assert auth._callback("/other?state=wrong", pending)[0] == 404
    assert auth._pending is pending
    respx.post(TOKEN_URL).respond(200, json={"access_token": "new", "expires_in": 3600})
    assert auth._callback(path, pending)[0] == 200
    assert auth._callback(path, pending)[0] == 400
    assert len(respx.calls) == 1


def test_login_timeout_rejects_callback(auth):
    path = callback_path(auth)
    pending = auth._pending
    pending.deadline = time.monotonic() - 1
    assert auth._callback(path, pending)[0] == 400


def test_cancelled_login_keeps_previous_token(auth, settings):
    auth.settings = replace(settings, access_token="previous")
    path = callback_path(auth, error="user_cancelled_login", error_description="secret-value")
    status, message = auth._callback(path, auth._pending)
    assert status == 400
    assert "secret-value" not in message
    assert "cancelled" in auth.status()["error"]
    assert auth.get_access_token() == "previous"


@respx.mock
def test_token_exchange_failure_never_echoes_provider_secrets(auth):
    respx.post(TOKEN_URL).respond(400, json={"error_description": "app-secret code-secret"})
    path = callback_path(auth)
    code, message = auth._callback(path, auth._pending)
    assert code == 400
    assert "app-secret" not in message + json.dumps(auth.status())
    assert "code-secret" not in message + json.dumps(auth.status())


@respx.mock
def test_expired_token_refreshes_and_preserves_refresh_expiry(settings):
    refresh_expiry = time.time() + 7200
    saved_tokens(settings, expires_at=0, refresh_token="refresh", refresh_expires_at=refresh_expiry)
    route = respx.post(TOKEN_URL).respond(200, json={"access_token": "renewed", "expires_in": 3600})
    manager = LinkedInAuth(settings)
    assert manager.get_access_token() == "renewed"
    assert manager.get_access_token() == "renewed"
    assert len(route.calls) == 1
    assert parse_qs(route.calls[0].request.content.decode())["grant_type"] == ["refresh_token"]
    assert manager._tokens["refresh_expires_at"] == refresh_expiry
    assert manager._tokens["refresh_token"] == "refresh"


@pytest.mark.parametrize("tokens", [
    {"expires_at": 0},
    {"expires_at": 0, "refresh_token": "refresh", "refresh_expires_at": 0},
])
def test_expired_credentials_require_login(settings, tokens):
    saved_tokens(settings, **tokens)
    with pytest.raises(LinkedInAuthError, match="linkedin_login"):
        LinkedInAuth(settings).get_access_token()


def test_saved_login_overrides_old_env_token_but_is_bound_to_app(settings):
    saved_tokens(settings)
    assert LinkedInAuth(replace(settings, access_token="stale-env")).get_access_token() == "old-token"
    with pytest.raises(LinkedInAuthError):
        LinkedInAuth(replace(settings, client_id="other-app")).get_access_token()


def test_corrupt_cache_allows_reconnecting(settings):
    settings.token_file.write_text("not-json")
    manager = LinkedInAuth(settings)
    assert manager.status()["status"] == "not_connected"
    assert "could not be read" in manager.status()["error"]


@respx.mock
def test_failed_persistence_does_not_report_success(auth, settings, monkeypatch):
    respx.post(TOKEN_URL).respond(200, json={"access_token": "new", "expires_in": 3600})
    monkeypatch.setattr("flin_linkedin_ads_mcp.auth.os.replace", lambda *_: (_ for _ in ()).throw(OSError()))
    path = callback_path(auth)
    code, message = auth._callback(path, auth._pending)
    assert code == 400
    assert "Could not save" in message
    assert not settings.token_file.exists()
    assert not list(settings.token_file.parent.glob(".linkedin-*"))


@respx.mock
@pytest.mark.parametrize("second_status", [200, 401])
def test_api_401_refreshes_once_and_uses_new_authorization(settings, second_status):
    saved_tokens(settings, refresh_token="refresh")
    manager = LinkedInAuth(settings)
    exchange = respx.post(TOKEN_URL).respond(200, json={"access_token": "renewed", "expires_in": 3600})
    api = respx.get("https://api.linkedin.com/rest/adAccounts")
    api.side_effect = [httpx.Response(401, json={"code": "EXPIRED_ACCESS_TOKEN"}),
                       httpx.Response(second_status, json={"elements": []})]
    with LinkedInClient(access_token="stale-env", api_version="202603",
                        restli_protocol_version="2.0.0", timeout_seconds=10,
                        max_retries=0, auth=manager) as client:
        if second_status == 200:
            assert client.get_json("adAccounts") == {"elements": []}
        else:
            with pytest.raises(LinkedInAuthError) as error:
                client.get_json("adAccounts")
            assert error.value.details["next_tool"] == "linkedin_login"
            assert manager.status()["status"] == "login_required"
    assert len(exchange.calls) == 1
    assert len(api.calls) == 2
    assert api.calls[0].request.headers["Authorization"] == "Bearer old-token"
    assert api.calls[1].request.headers["Authorization"] == "Bearer renewed"


@respx.mock
def test_invalid_refresh_token_returns_reconnect_guidance(settings):
    saved_tokens(settings, expires_at=0, refresh_token="refresh")
    route = respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant"})
    manager = LinkedInAuth(settings)
    with pytest.raises(LinkedInAuthError, match="linkedin_login"):
        manager.get_access_token()
    assert len(route.calls) == 1
    assert "token exchange failed" in manager.status()["error"]


def test_busy_callback_port_has_actionable_error(auth, settings):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", urlsplit(settings.redirect_uri).port))
        sock.listen()
        with pytest.raises(LinkedInAuthError, match="Cannot open the local login callback"):
            auth.login()
