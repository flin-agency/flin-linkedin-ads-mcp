from __future__ import annotations

import pytest

from flin_linkedin_ads_mcp.config import load_config


def test_load_config_allows_starting_before_login() -> None:
    assert load_config({}).access_token == ""


def test_load_config_accepts_oauth_without_static_token() -> None:
    settings = load_config({"LINKEDIN_CLIENT_ID": "app", "LINKEDIN_CLIENT_SECRET": "secret"})
    assert settings.client_id == "app"
    assert "secret" not in repr(settings)


@pytest.mark.parametrize("env", [
    {"LINKEDIN_CLIENT_ID": "app"}, {"LINKEDIN_CLIENT_SECRET": "secret"},
    {"LINKEDIN_REDIRECT_URI": "http://example.com:9876/callback"},
    {"LINKEDIN_REDIRECT_URI": "http://localhost/callback"},
    {"LINKEDIN_REDIRECT_URI": "http://localhost:9876/callback?extra=yes"},
    {"LINKEDIN_REDIRECT_URI": "http://user@localhost:9876/callback"},
])
def test_load_config_rejects_invalid_oauth_configuration(env) -> None:
    with pytest.raises(ValueError):
        load_config(env)


def test_load_config_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "token")
    monkeypatch.delenv("LINKEDIN_API_VERSION", raising=False)
    monkeypatch.delenv("LINKEDIN_RESTLI_PROTOCOL_VERSION", raising=False)
    monkeypatch.delenv("LINKEDIN_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LINKEDIN_MAX_RETRIES", raising=False)

    settings = load_config()

    assert settings.access_token == "token"
    assert settings.api_version == "202603"
    assert settings.restli_protocol_version == "2.0.0"
    assert settings.timeout_seconds == 30.0
    assert settings.max_retries == 3
