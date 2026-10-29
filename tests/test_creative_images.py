from __future__ import annotations

import pytest
import respx

from flin_linkedin_ads_mcp.config import load_config
from flin_linkedin_ads_mcp.dispatcher import dispatch_tool
from flin_linkedin_ads_mcp.errors import LinkedInPermissionError, LinkedInValidationError
from flin_linkedin_ads_mcp.linkedin_client import LinkedInClient


BASE = "https://api.linkedin.com/rest/"
CREATIVE = "adAccounts/123/creatives/urn%3Ali%3AsponsoredCreative%3A456"
IMAGE = "https://media.licdn.com/dms/image/v2/example/feedshare-shrink_800"


@pytest.fixture
def client():
    with LinkedInClient(
        access_token="test-token", api_version="202610", restli_protocol_version="2.0.0",
        timeout_seconds=10, max_retries=0,
    ) as client:
        yield client


def call(client, name, arguments, version="202610"):
    return dispatch_tool(
        name, arguments, client=client, settings=load_config({"LINKEDIN_API_VERSION": version}),
    )


@respx.mock
def test_single_creative_uses_metadata_without_posts_permissions(client):
    route = respx.get(BASE + CREATIVE).respond(200, json={
        "id": "urn:li:sponsoredCreative:456", "name": "Example",
        "metadata": {"assetURL": IMAGE, "adHeadline": "Headline", "adFormat": "SINGLE_IMAGE"},
        "content": {"standardUpdateAd": {"reference": "urn:li:share:789"}},
    })
    result = call(client, "get_creative", {
        "ad_account_id": "123", "id": "456", "fields": ["id", "imageUrl", "metadata"],
    })
    assert result["data"]["imageUrl"] == IMAGE
    assert result["data"]["metadata"]["adHeadline"] == "Headline"
    assert "content" not in result["data"]
    assert route.calls[0].request.url.params["fields"] == "id,content,metadata"
    assert route.calls[0].request.url.query == b"fields=id,content,metadata"
    assert route.calls[0].request.headers["Linkedin-Version"] == "202610"
    assert len(respx.calls) == 1


@respx.mock
def test_listing_hydrates_and_deduplicates_metadata_and_keeps_paging(client):
    creative = {"id": "urn:li:sponsoredCreative:456"}
    respx.get(BASE + "adAccounts/123/creatives").respond(200, json={
        "elements": [creative, creative], "metadata": {"nextPageToken": "next-page"},
    })
    details = respx.get(BASE + CREATIVE).respond(200, json={"metadata": {"assetURL": IMAGE}})
    result = call(client, "list_creatives", {
        "ad_account_id": "123", "fields": ["id", "imageUrl"],
    })
    assert result["data"] == [{"id": creative["id"], "imageUrl": IMAGE}] * 2
    assert details.call_count == 1
    assert details.calls[0].request.url.query == b"fields=id,metadata"
    assert result["paging"] == {"has_next": True, "next_after": "next-page"}


@respx.mock
def test_default_listing_does_not_fetch_metadata(client):
    respx.get(BASE + "adAccounts/123/creatives").respond(200, json={
        "elements": [{"id": "urn:li:sponsoredCreative:456"}],
    })
    call(client, "list_creatives", {"ad_account_id": "123"})
    assert len(respx.calls) == 1


@pytest.mark.parametrize("name", ["get_creative", "list_creatives"])
@respx.mock
def test_explicit_metadata_on_old_version_is_rejected_before_request(client, name):
    with pytest.raises(ValueError, match="202610"):
        call(client, name, {
            "ad_account_id": "123", "id": "456", "fields": ["metadata"],
        }, version="202603")
    assert not respx.calls


@respx.mock
def test_legacy_version_image_resolution_does_not_project_metadata(client):
    route = respx.get(BASE + CREATIVE).respond(200, json={"content": {"imageUrl": IMAGE}})
    result = call(client, "get_creative", {
        "ad_account_id": "123", "id": "456", "fields": ["imageUrl"],
    }, version="202603")
    assert "fields" not in route.calls[0].request.url.params
    assert result["data"]["imageUrl"] == IMAGE


@respx.mock
def test_ugc_post_image_urns_are_resolved_once(client):
    respx.get(BASE + "posts/urn%3Ali%3AugcPost%3A789").respond(200, json={
        "commentary": "Post text",
        "content": {"multiImage": {"images": [
            {"id": "urn:li:image:abc"}, {"id": "urn:li:image:abc"},
        ]}},
    })
    image = respx.get(BASE + "images/urn%3Ali%3Aimage%3Aabc").respond(
        200, json={"downloadUrl": IMAGE, "downloadUrlExpiresAt": 9999999999999},
    )
    result = call(client, "get_share_content", {"share_urn": "urn:li:ugcPost:789"})
    assert result["data"]["text"] == "Post text"
    assert result["data"]["image_urls"] == [IMAGE]
    assert image.call_count == 1


@respx.mock
def test_nested_creative_post_reference_uses_modern_images(client):
    respx.get(BASE + CREATIVE).respond(200, json={
        "content": {"standardUpdateAd": {"reference": "urn:li:ugcPost:789"}},
    })
    respx.get(BASE + "posts/urn%3Ali%3AugcPost%3A789").respond(200, json={
        "content": {"media": {"id": "urn:li:image:abc"}},
    })
    respx.get(BASE + "images/urn%3Ali%3Aimage%3Aabc").respond(200, json={"downloadUrl": IMAGE})
    result = call(client, "get_creative", {
        "ad_account_id": "123", "id": "456", "fields": ["imageUrl"],
    })
    assert result["data"]["imageUrl"] == IMAGE


@respx.mock
def test_post_permission_failure_is_not_misreported_as_old_api(client):
    respx.get(BASE + "posts/urn%3Ali%3Ashare%3A789").respond(
        403, json={"message": "Not enough permissions to access Posts"},
    )
    with pytest.raises(LinkedInPermissionError):
        call(client, "get_share_content", {"share_urn": "urn:li:share:789"})
    assert len(respx.calls) == 1


@respx.mock
def test_video_asset_is_not_returned_as_image(client):
    respx.get(BASE + CREATIVE).respond(200, json={
        "metadata": {"assetURL": "https://media.licdn.com/example.mp4"},
    })
    result = call(client, "get_creative", {
        "ad_account_id": "123", "id": "456", "fields": ["imageUrl"],
    })
    assert result["data"]["imageUrl"] is None


@respx.mock
def test_inactive_version_error_has_configuration_guidance(client):
    respx.get(BASE + CREATIVE).respond(426, json={
        "message": "Requested version is not active", "code": "NONEXISTENT_VERSION",
    })
    with pytest.raises(LinkedInValidationError, match="LINKEDIN_API_VERSION=202610") as error:
        call(client, "get_creative", {"ad_account_id": "123", "id": "456"})
    assert error.value.details["error"]["code"] == "NONEXISTENT_VERSION"
