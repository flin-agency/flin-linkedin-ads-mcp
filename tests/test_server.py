from __future__ import annotations

import asyncio
import json

from flin_linkedin_ads_mcp import server
from flin_linkedin_ads_mcp.config import LinkedInAdsSettings, load_config


class _DummyTextContent:
    def __init__(self, *, type: str, text: str) -> None:
        self.type = type
        self.text = text


class _DummyMcpTypes:
    TextContent = _DummyTextContent

    class Tool:
        def __init__(self, *, name: str, description: str, inputSchema: dict) -> None:
            self.name = name
            self.description = description
            self.inputSchema = inputSchema


class _DummyServer:
    def __init__(self, _: str) -> None:
        self.call_tool_handler = None
        self.list_tools_handler = None

    def list_tools(self):
        def decorator(func):
            self.list_tools_handler = func
            return func

        return decorator

    def call_tool(self):
        def decorator(func):
            self.call_tool_handler = func
            return func

        return decorator


def test_call_tool_unexpected_exception_does_not_leak_internal_error_details(monkeypatch) -> None:
    def _boom(*_, **__):
        raise RuntimeError("sensitive backend failure")

    monkeypatch.setattr(server, "Server", _DummyServer)
    monkeypatch.setattr(server, "mcp_types", _DummyMcpTypes)
    monkeypatch.setattr(server, "dispatch_tool", _boom)

    settings = LinkedInAdsSettings(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )
    client = type("ClientStub", (), {"last_request_id": "req-123"})()

    test_server = server.create_server(settings=settings, client=client)
    response_chunks = asyncio.run(test_server.call_tool_handler("list_campaigns", {}))
    payload = json.loads(response_chunks[0].text)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "linkedin_api_error"
    assert payload["error"]["message"] == "Unexpected server error"
    assert payload["error"]["details"] == {}
    assert "sensitive backend failure" not in response_chunks[0].text


def test_auth_tools_available_without_token_and_return_setup_guidance(monkeypatch) -> None:
    monkeypatch.setattr(server, "Server", _DummyServer)
    monkeypatch.setattr(server, "mcp_types", _DummyMcpTypes)
    settings = load_config({})
    with server._client(settings) as client:
        app = server.create_server(settings, client)
        listed = asyncio.run(app.list_tools_handler())
        assert {"linkedin_login", "linkedin_login_status"} <= {tool.name for tool in listed}
        status = json.loads(asyncio.run(app.call_tool_handler("linkedin_login_status", {}))[0].text)
        assert status["ok"] is True
        assert status["data"]["status"] == "not_connected"
        login = json.loads(asyncio.run(app.call_tool_handler("linkedin_login", {}))[0].text)
        assert login["error"]["code"] == "auth_error"
        assert "LINKEDIN_CLIENT_ID" in login["error"]["message"]
        ads = json.loads(asyncio.run(app.call_tool_handler("list_ad_accounts", {}))[0].text)
        assert ads["error"]["details"]["next_tool"] == "linkedin_login"
        bad = json.loads(asyncio.run(app.call_tool_handler("linkedin_login", {"token": "secret"}))[0].text)
        assert bad["error"]["code"] == "validation_error"
        assert "secret" not in json.dumps(bad)


def test_auth_tool_routes_to_live_manager(monkeypatch) -> None:
    monkeypatch.setattr(server, "Server", _DummyServer)
    monkeypatch.setattr(server, "mcp_types", _DummyMcpTypes)
    settings = load_config({})
    with server._client(settings) as client:
        monkeypatch.setattr(client.auth, "login", lambda: {"authorization_url": "https://example.test"})
        app = server.create_server(settings, client)
        result = json.loads(asyncio.run(app.call_tool_handler("linkedin_login", {}))[0].text)
        assert result["data"]["authorization_url"] == "https://example.test"
