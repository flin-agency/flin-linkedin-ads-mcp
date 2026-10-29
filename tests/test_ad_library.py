from __future__ import annotations

import pytest
import respx

from flin_linkedin_ads_mcp.config import load_config
from flin_linkedin_ads_mcp.dispatcher import dispatch_tool
from flin_linkedin_ads_mcp.errors import LinkedInPermissionError
from flin_linkedin_ads_mcp.linkedin_client import LinkedInClient


@pytest.fixture
def client():
    with LinkedInClient(
        access_token="test-token", api_version="202603", restli_protocol_version="2.0.0",
        timeout_seconds=10, max_retries=0,
    ) as client:
        yield client


def call(client, arguments, name="search_ad_library"):
    return dispatch_tool(name, arguments, settings=load_config({}), client=client)


@respx.mock
def test_ads_filters_wire_encoding_and_transparency_data(client):
    ad = {
        "adUrl": "https://www.linkedin.com/ad-library/detail/123",
        "details": {
            "advertiser": {"advertiserName": "Example", "adPayer": "Example"},
            "type": "TEXT_AD", "adTargeting": [{"facetName": "Language"}],
            "adStatistics": {"totalImpressions": {"from": 1000, "to": 5000}},
        },
        "isRestricted": True, "restrictionDetails": "Restricted by LinkedIn",
    }
    route = respx.get("https://api.linkedin.com/rest/adLibrary").respond(
        200, json={"elements": [ad]}, headers={"x-li-request-id": "library-1"},
    )
    result = call(client, {
        "keyword": "health & technology+(AI),ä", "advertiser": "A&B", "payer_name": "ACME",
        "countries": ["CH", "de", "CH"], "date_from": "2026-10-01", "date_to": "2026-10-29",
        "included_targeting_categories": ["COMPANY", "LANGUAGE"],
        "excluded_targeting_categories": ["JOB"], "impressions_from": 1000,
        "impressions_to": 5000, "sort_order": "ASCENDING", "page_size": 2,
    })
    assert len(respx.calls) == 1  # No ad account discovery or content follow-up.
    request = route.calls[0].request
    assert request.method == "GET"
    assert request.headers["Authorization"] == "Bearer test-token"
    assert request.headers["Linkedin-Version"] == "202603"
    assert request.headers["X-RestLi-Method"] == "FINDER"
    assert dict(request.url.params) == {
        "q": "criteria", "keyword": "health & technology+(AI),ä", "advertiser": "A&B",
        "payerName": "ACME", "countries": "(value:List(urn:li:country:ch,urn:li:country:de))",
        "dateRange": "(start:(year:2026,month:10,day:1),end:(year:2026,month:10,day:29))",
        "includedTargetingFacetCategories": "List(COMPANY,LANGUAGE)",
        "excludedTargetingFacetCategories": "List(JOB)",
        "totalImpressionsRange": "(from:1000,to:5000)",
        "sortBy": "(order:ASCENDING,field:CREATED_TIME)", "start": "0", "count": "2",
    }
    assert b"countries=(value:List(urn%3Ali%3Acountry%3Ach," in request.url.query
    assert b"keyword=health%20%26%20technology%2B%28AI%29%2C%C3%A4" in request.url.query
    assert result["data"] == [ad]
    assert result["meta"]["request_id"] == "library-1"
    assert result["paging"]["has_next"] is False


@respx.mock
def test_ads_defaults_and_open_impression_range(client):
    route = respx.get("https://api.linkedin.com/rest/adLibrary").respond(200, json={"elements": []})
    call(client, {"impressions_from": 1000000, "impressions_to": 0})
    params = route.calls[0].request.url.params
    assert params["totalImpressionsRange"] == "(from:1000000,to:0)"
    assert params["count"] == "25"
    assert params["start"] == "0"
    assert "dateRange" not in params


@pytest.mark.parametrize("arguments", [
    {"keyword": " "}, {"advertiser": 123}, {"payer_name": None},
    {"countries": "DE"}, {"countries": []}, {"countries": ["DE),x:(y"]},
    {"countries": [123]}, {"date_from": "2026-10-01"}, {"date_to": "2026-10-02"},
    {"date_from": "2026-02-30", "date_to": "2026-03-01"},
    {"date_from": "2026-10-02", "date_to": "2026-10-01"},
    {"date_from": "2026-10-01", "date_to": "2026-10-01"},
    {"included_targeting_categories": ["INVALID"]}, {"excluded_targeting_categories": []},
    {"included_targeting_categories": "COMPANY"}, {"impressions_from": 1},
    {"impressions_from": 5000, "impressions_to": 1000},
    {"impressions_from": 0, "impressions_to": 0},
    {"impressions_from": True, "impressions_to": 1000},
    {"sort_order": "latest"}, {"page_size": 26}, {"page_size": 0},
    {"page_size": True}, {"page_start": -1}, {"page_start": "25"},
])
@respx.mock
def test_invalid_ads_arguments_do_not_make_requests(client, arguments):
    with pytest.raises(ValueError):
        call(client, arguments)
    assert not respx.calls


@pytest.mark.parametrize(("paging", "returned", "expected"), [
    ({"total": 5}, 2, 4),
    ({"total": 4}, 2, None),
    ({"total": 50}, 0, None),
    ({}, 2, 4),
    ({}, 1, None),
    ({"total": "unknown"}, 1, None),
    ({"links": [{"rel": "next", "href": "/adLibrary?start=8"}]}, 1, 8),
    ({"links": [{"rel": "next", "href": "/adLibrary?start=2"}], "total": 5}, 2, 4),
    ({"links": [{"rel": "next", "href": "/adLibrary?start=bogus"}], "total": 5}, 2, 4),
    ({"links": None}, 1, None),
])
@respx.mock
def test_offset_pagination(client, paging, returned, expected):
    respx.get("https://api.linkedin.com/rest/adLibrary").respond(
        200, json={"elements": [{"adUrl": "example"}] * returned, "paging": paging},
    )
    result = call(client, {"page_start": 2, "page_size": 2})
    assert result["paging"]["next_start"] == expected
    assert result["paging"]["next_after"] == (str(expected) if expected is not None else None)
    assert result["paging"]["has_next"] is (expected is not None)
    assert len(respx.calls) == 1


@respx.mock
def test_partnerships_and_second_page(client):
    route = respx.get("https://api.linkedin.com/rest/paidEndorsementPosts").respond(
        200, json={"elements": [{"postUrl": "https://www.linkedin.com/feed/update/example"}],
                   "paging": {"total": 2}},
    )
    result = call(client, {
        "keyword": "technology & AI", "date_range": "PAST_WEEK", "page_size": 1,
    }, "search_brand_partnerships")
    assert dict(route.calls[0].request.url.params) == {
        "q": "searchCriteria", "keyword": "technology & AI", "dateRange": "PAST_WEEK",
        "start": "0", "count": "1",
    }
    assert result["data"][0]["postUrl"].startswith("https://www.linkedin.com/")
    result = call(client, {
        "keyword": "technology & AI", "date_range": "PAST_WEEK", "page_size": 1,
        "page_start": result["paging"]["next_start"],
    }, "search_brand_partnerships")
    assert route.calls[1].request.url.params["start"] == "1"
    assert result["paging"]["has_next"] is False


@pytest.mark.parametrize("arguments", [{}, {"keyword": ""}, {"keyword": 123},
                                       {"keyword": "AI", "date_range": "ALL"}])
@respx.mock
def test_invalid_partnership_arguments(client, arguments):
    with pytest.raises(ValueError):
        call(client, arguments, "search_brand_partnerships")
    assert not respx.calls


@pytest.mark.parametrize(("name", "endpoint", "arguments"), [
    ("search_ad_library", "adLibrary", {}),
    ("search_brand_partnerships", "paidEndorsementPosts", {"keyword": "AI"}),
])
@respx.mock
def test_product_permission_error_preserves_diagnostics(client, name, endpoint, arguments):
    respx.get(f"https://api.linkedin.com/rest/{endpoint}").respond(
        403, json={"message": "Access denied"}, headers={"x-li-request-id": "denied-1"},
    )
    with pytest.raises(LinkedInPermissionError, match="Ad Library product") as error:
        call(client, arguments, name)
    assert error.value.status_code == 403
    assert error.value.request_id == "denied-1"
    assert error.value.details["error"]["message"] == "Access denied"
