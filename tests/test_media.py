from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import httpx
from mcp import types
import pytest
import respx

from flin_linkedin_ads_mcp import server
from flin_linkedin_ads_mcp.config import load_config
from flin_linkedin_ads_mcp.dispatcher import dispatch_tool
from flin_linkedin_ads_mcp.errors import (
    LinkedInAPIError, LinkedInPermissionError, LinkedInValidationError,
)
from flin_linkedin_ads_mcp.linkedin_client import LinkedInClient
from flin_linkedin_ads_mcp.tools import media
from test_server import _DummyServer

BASE = "https://api.linkedin.com/rest/"
CREATIVE = BASE + "adAccounts/123/creatives/urn%3Ali%3AsponsoredCreative%3A456"
POST = BASE + "posts/urn%3Ali%3AugcPost%3A789"
VIDEO = BASE + "videos/urn%3Ali%3Avideo%3Aabc"
IMAGE_URL = "https://media.licdn.com/dms/image/example?signature=private"
VIDEO_URL = "https://dms.licdn.com/playlist/example"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
)
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 20


@pytest.fixture
def setup(tmp_path):
    settings = load_config({"LINKEDIN_MEDIA_DIR": str(tmp_path / "media")})
    with LinkedInClient(
        access_token="private-api-token", api_version="202610", restli_protocol_version="2.0.0",
        timeout_seconds=10, max_retries=0,
    ) as client:
        yield client, settings


def call(setup, **arguments):
    client, settings = setup
    result = dispatch_tool("get_creative_media", {
        "ad_account_id": "123", "id": "456", **arguments,
    }, client=client, settings=settings)
    assert isinstance(result, media.MediaResult)
    return result


def mock_preview():
    respx.get(CREATIVE).respond(200, json={
        "id": "urn:li:sponsoredCreative:456",
        "metadata": {"assetURL": IMAGE_URL, "adFormat": "SPONSORED_VIDEO"},
        "content": {"videoAd": {"reference": "urn:li:ugcPost:789"}},
    })
    return respx.get(IMAGE_URL).respond(200, content=PNG, headers={"content-type": "image/png"})


@respx.mock
@pytest.mark.parametrize("output", ["inline", "file", "both"])
def test_preview_outputs_and_no_api_token_at_cdn(setup, output):
    cdn = mock_preview()
    result = call(setup, output=output)
    data = result.response["data"]
    assert data["mime_type"] == "image/png"
    assert data["kind"] == "preview"
    assert data["size_bytes"] == len(PNG)
    assert (result.image == PNG) is (output != "file")
    assert "authorization" not in cdn.calls[0].request.headers
    assert "linkedin-version" not in cdn.calls[0].request.headers
    assert "signature" not in json.dumps(result.response)
    if output != "inline":
        path = Path(data["local_path"])
        assert path.read_bytes() == PNG
        assert path.stat().st_mode & 0o777 == 0o600
        assert data["file_uri"] == path.as_uri()
    else:
        assert not setup[1].media_dir.exists()
    assert len(respx.calls) == 2  # Video thumbnails do not require Posts access.


@respx.mock
def test_video_uses_video_api_and_returns_file(setup):
    mock_preview()
    respx.get(POST).respond(200, json={"content": {"media": {"id": "urn:li:video:abc"}}})
    respx.get(VIDEO).respond(200, json={
        "status": "AVAILABLE", "downloadUrl": VIDEO_URL, "downloadUrlExpiresAt": 123456789,
    })
    respx.get(VIDEO_URL).respond(200, content=MP4, headers={"content-type": "video/mp4"})
    result = call(setup, kind="video")
    assert result.image is None
    assert result.response["data"]["download_url_expires_at"] == 123456789
    assert Path(result.response["data"]["local_path"]).read_bytes() == MP4


@respx.mock
@pytest.mark.parametrize("endpoint", [POST, VIDEO])
def test_video_permission_error_keeps_preview_guidance(setup, endpoint):
    mock_preview()
    if endpoint == VIDEO:
        respx.get(POST).respond(200, json={"content": {"media": {"id": "urn:li:video:abc"}}})
    respx.get(endpoint).respond(403, json={"message": "Not enough permissions"})
    with pytest.raises(LinkedInPermissionError, match="kind=preview"):
        call(setup, kind="video")
    assert not setup[1].media_dir.exists()


@pytest.mark.parametrize("url", [
    "http://media.licdn.com/image", "https://localhost/image", "https://127.0.0.1/image",
    "https://media.licdn.com.evil.test/image", "https://user:pass@media.licdn.com/image",
    "https://media.licdn.com:8080/image", "file:///tmp/image", "https://example.com/media.licdn.com",
])
def test_rejects_unsafe_destinations(url):
    with pytest.raises(LinkedInValidationError):
        media._validate_url(url)


@respx.mock
def test_redirect_target_is_validated_before_request(setup):
    mock_preview()
    respx.get(IMAGE_URL).respond(302, headers={"location": "http://127.0.0.1/private"})
    with pytest.raises(LinkedInValidationError, match="CDN"):
        call(setup)
    assert len(respx.calls) == 2


@respx.mock
def test_allowed_redirect(setup):
    mock_preview()
    respx.get(IMAGE_URL).respond(302, headers={"location": "https://media.licdn.com/next"})
    respx.get("https://media.licdn.com/next").respond(200, content=PNG, headers={"content-type": "image/png"})
    assert call(setup).image == PNG


@respx.mock
@pytest.mark.parametrize("mime,body", [
    ("text/html", b"<html>"), ("image/svg+xml", b"<svg/>"),
    ("image/png", b"<html>"), ("video/mp4", MP4),
])
def test_wrong_file_type_does_not_write(setup, mime, body):
    mock_preview()
    respx.get(IMAGE_URL).respond(200, content=body, headers={"content-type": mime})
    with pytest.raises(LinkedInValidationError):
        call(setup)
    assert not setup[1].media_dir.exists()


@respx.mock
@pytest.mark.parametrize("declared_length", [False, True])
def test_download_size_limit_with_and_without_length(setup, monkeypatch, declared_length):
    mock_preview()
    monkeypatch.setattr(media, "IMAGE_LIMIT", 10)
    headers = {"content-type": "image/png"}
    if declared_length:
        headers["content-length"] = "1000"
    respx.get(IMAGE_URL).mock(return_value=httpx.Response(
        200, stream=httpx.ByteStream(PNG), headers=headers,
    ))
    with pytest.raises(LinkedInValidationError, match="limit"):
        call(setup)
    assert not setup[1].media_dir.exists()


@respx.mock
def test_download_error_does_not_expose_signed_url(setup):
    mock_preview()
    respx.get(IMAGE_URL).mock(side_effect=httpx.ConnectError(IMAGE_URL))
    with pytest.raises(LinkedInAPIError) as error:
        call(setup)
    assert "signature" not in str(error.value)


@respx.mock
def test_expired_url_is_resolved_again_on_next_call(setup):
    mock_preview()
    respx.get(IMAGE_URL).respond(403)
    with pytest.raises(LinkedInAPIError, match="fresh URL"):
        call(setup)
    fresh = "https://media.licdn.com/new.png"
    respx.get(CREATIVE).respond(200, json={"id": "456", "metadata": {"assetURL": fresh}})
    respx.get(fresh).respond(200, content=PNG, headers={"content-type": "image/png"})
    assert call(setup).image == PNG


@respx.mock
def test_native_mcp_image_and_file_link(setup, monkeypatch):
    mock_preview()
    monkeypatch.setattr(server, "Server", _DummyServer)
    app = server.create_server(settings=setup[1], client=setup[0])
    chunks = asyncio.run(app.call_tool_handler("get_creative_media", {"id": "456", "ad_account_id": "123"}))
    assert isinstance(chunks[0], types.TextContent)
    assert isinstance(chunks[1], types.ImageContent)
    assert base64.b64decode(chunks[1].data) == PNG
    assert isinstance(chunks[2], types.ResourceLink)
    assert chunks[2].mimeType == "image/png"
    assert "iVBOR" not in chunks[0].text


@respx.mock
def test_inline_video_is_rejected_before_api_calls(setup):
    with pytest.raises(ValueError, match="output=file"):
        call(setup, kind="video", output="inline")
    assert not respx.calls
