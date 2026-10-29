from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import unquote

import pytest

from flin_linkedin_ads_mcp.config import LinkedInAdsSettings
from flin_linkedin_ads_mcp.errors import LinkedInValidationError
from flin_linkedin_ads_mcp.errors import AccountSelectionRequired
from flin_linkedin_ads_mcp.tools.account_intelligence import list_account_intelligence
from flin_linkedin_ads_mcp.tools.campaigns import get_campaign, list_campaigns
from flin_linkedin_ads_mcp.tools.creatives import get_creative, list_creatives
from flin_linkedin_ads_mcp.tools.insights import get_insights
from flin_linkedin_ads_mcp.tools.share_content import get_share_content


@dataclass
class DummyClient:
    calls: list[tuple[str, dict]]
    ad_accounts: list[str] = field(default_factory=lambda: ["111"])
    last_request_id: str | None = None

    def get_json(self, path: str, params: dict | None) -> dict:
        self.calls.append((path, dict(params or {})))
        if path == "adAccounts":
            return {
                "elements": [
                    {
                        "id": int(account_id.split(":")[-1]),
                        "name": f"Account {account_id}",
                    }
                    for account_id in self.ad_accounts
                ]
            }
        if path.endswith("/creatives"):
            return {"elements": [{"id": "urn:li:sponsoredCreative:999", "name": "Creative"}]}
        if "/creatives/" in path:
            encoded_id = path.rsplit("/", 1)[-1]
            return {
                "id": unquote(encoded_id),
                "name": "Creative",
                "campaign": "urn:li:sponsoredCampaign:469031486",
                "content": {"reference": "urn:li:share:123"},
            }
        if path.startswith("accountIntelligence?"):
            return {
                "elements": [
                    {
                        "companyName": "Microsoft",
                        "paidImpressions": 133,
                        "paidClicks": 20,
                        "paidQualifiedLeads": 5,
                        "conversions": 12,
                    }
                ]
            }
        return {"elements": []}


@pytest.fixture
def settings() -> LinkedInAdsSettings:
    return LinkedInAdsSettings(
        access_token="token",
        api_version="202602",
        restli_protocol_version="2.0.0",
        timeout_seconds=10,
        max_retries=1,
    )


def test_list_campaigns_prefers_per_call_ad_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_campaigns(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "urn:li:sponsoredAccount:222", "page_size": 10},
    )

    assert result["ok"] is True
    assert client.calls == [("adAccounts/222/adCampaigns", {"q": "search", "pageSize": 10})]


def test_list_campaigns_auto_resolves_single_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_campaigns(client=client, settings=settings, arguments={})

    assert result["ok"] is True
    assert client.calls[0] == ("adAccounts", {"q": "search", "pageSize": 1000})
    assert client.calls[1] == ("adAccounts/111/adCampaigns", {"q": "search", "pageSize": 100})


def test_get_insights_passes_entity_filters(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "entity_ids": ["123", "urn:li:sponsoredCampaign:456"], "date_from": "2025-01-01"},
    )

    assert result["ok"] is True
    path, params = client.calls[1]
    assert path.startswith("adAnalytics?")
    assert "q=analytics" in path
    assert "pivot.value=CAMPAIGN" in path
    assert "timeGranularity.value=DAILY" in path
    assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A123,urn%3Ali%3AsponsoredCampaign%3A456)" in path
    assert "fields=account_id,campaign_id,adset_id,ad_id,impressions,clicks,spend,reach,frequency,cpc,ctr" not in path
    assert "%2C" not in path
    assert params == {}


def test_list_campaigns_requires_ad_account_id_when_multiple_accounts_exist(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[], ad_accounts=["111", "222"])

    with pytest.raises(AccountSelectionRequired) as exc_info:
        list_campaigns(client=client, settings=settings, arguments={})

    assert [choice["ad_account_id"] for choice in exc_info.value.choices] == [
        "urn:li:sponsoredAccount:111",
        "urn:li:sponsoredAccount:222",
    ]


def test_get_campaign_rejects_invalid_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="supported format"):
        get_campaign(client=client, settings=settings, arguments={"id": "act_111/campaigns"})


def test_list_campaigns_rejects_invalid_ad_account_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="supported format"):
        list_campaigns(client=client, settings=settings, arguments={"ad_account_id": "foo"})


def test_list_campaigns_rejects_unknown_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="Unsupported fields"):
        list_campaigns(
            client=client,
            settings=settings,
            arguments={"ad_account_id": "urn:li:sponsoredAccount:222", "fields": ["id", "not_a_real_field"]},
        )


def test_get_insights_rejects_unknown_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="Unsupported fields"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign", "fields": ["impressions", "not_a_real_metric"]},
        )


def test_get_insights_requires_date_from(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="date_from is required"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign"},
        )


def test_get_insights_accepts_landing_page_clicks_field(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "pivot": "campaign",
            "date_from": "2025-01-01",
            "fields": ["impressions", "landingPageClicks", "costInLocalCurrency"],
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=impressions,landingPageClicks,costInLocalCurrency" in path


def test_get_insights_accepts_extended_reporting_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "date_from": "2025-01-01", "fields": ["totalEngagements", "oneClickLeads", "costInUsd"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=totalEngagements,oneClickLeads,costInUsd" in path


def test_get_insights_accepts_pivot_value_alias(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "date_from": "2025-01-01", "fields": ["impressions", "pivotValue"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=impressions,pivotValues" in path


def test_get_insights_accepts_ctr_and_cpc_compat_fields(settings: LinkedInAdsSettings) -> None:
    class DerivedMetricsClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "adAccounts":
                return {"elements": [{"id": 508834004, "name": "Account"}]}
            return {
                "elements": [
                    {
                        "impressions": 100,
                        "clicks": 5,
                        "costInLocalCurrency": "12.5",
                        "pivotValues": ["urn:li:sponsoredCreative:999"],
                    }
                ]
            }

    client = DerivedMetricsClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "creative",
            "date_from": "2025-12-01",
            "date_to": "2025-12-31",
            "time_granularity": "ALL",
            "fields": [
                "costInLocalCurrency",
                "impressions",
                "clicks",
                "clickThroughRate",
                "costPerClick",
                "pivotValue",
            ],
            "sort_by_field": "IMPRESSIONS",
            "sort_order": "DESCENDING",
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[0]
    assert "fields=costInLocalCurrency,impressions,clicks,pivotValues" in path
    assert "clickThroughRate" not in path
    assert "costPerClick" not in path

    row = result["data"][0]
    assert row["clickThroughRate"] == pytest.approx(0.05)
    assert row["costPerClick"] == pytest.approx(2.5)
    assert row["pivotValues"] == ["urn:li:sponsoredCreative:999"]


def test_get_insights_accepts_yearly_time_granularity(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "date_from": "2025-01-01", "time_granularity": "YEARLY", "fields": ["impressions", "clicks"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "timeGranularity.value=YEARLY" in path


def test_get_insights_accepts_member_demographic_pivot(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "member_company_size", "date_from": "2025-01-01", "fields": ["impressions", "costInLocalCurrency"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "pivot.value=MEMBER_COMPANY_SIZE" in path


def test_get_insights_accepts_action_clicks_metric(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={"pivot": "campaign", "date_from": "2025-01-01", "fields": ["impressions", "actionClicks"]},
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=impressions,actionClicks" in path


def test_get_insights_accepts_video_and_event_metrics(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "pivot": "campaign",
            "date_from": "2025-01-01",
            "fields": ["videoWatchTime", "averageVideoWatchTime", "eventViews", "eventWatchTime"],
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[1]
    assert "fields=videoWatchTime,averageVideoWatchTime,eventViews,eventWatchTime" in path


def test_get_insights_omits_default_account_facet_when_campaigns_are_explicit(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "campaign",
            "campaign_ids": ["456070296", "469031486"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "time_granularity": "ALL",
        },
    )

    assert result["ok"] is True
    path, _ = client.calls[0]
    assert "campaigns=List(urn%3Ali%3AsponsoredCampaign%3A456070296,urn%3Ali%3AsponsoredCampaign%3A469031486)" in path
    assert "accounts=List(" not in path


def test_get_insights_retries_query_shapes_for_illegal_argument(settings: LinkedInAdsSettings) -> None:
    class QueryShapeFlakyClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "adAccounts":
                return {"elements": [{"id": 508834004, "name": "Account"}]}
            if len(self.calls) < 8:
                raise LinkedInValidationError(
                    "Invalid query parameters passed to request",
                    status_code=400,
                    details={
                        "status_code": 400,
                        "error": {"code": "ILLEGAL_ARGUMENT", "message": "Invalid query parameters passed to request"},
                    },
                )
            return {"elements": []}

    client = QueryShapeFlakyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "campaign",
            "campaign_ids": ["456070296"],
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "time_granularity": "DAILY",
        },
    )

    assert result["ok"] is True
    called_paths = [path for path, _ in client.calls]
    assert called_paths[0].startswith("adAnalytics?")
    assert "pivot.value=CAMPAIGN" in called_paths[0]
    assert "pivot=CAMPAIGN" in called_paths[1]
    assert "accounts=List(" in called_paths[2]
    assert "dateRange=(start:(day:1,month:1,year:2025),end:(day:31,month:12,year:2025))" in called_paths[-1]


def test_get_insights_retries_when_query_params_are_not_allowed(settings: LinkedInAdsSettings) -> None:
    class QueryParamNotAllowedFlakyClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "adAccounts":
                return {"elements": [{"id": 508834004, "name": "Account"}]}
            if "sortBy.field=" in path or "sortBy.order=" in path:
                raise LinkedInValidationError(
                    "Multiple errors occurred during param validation. Please see errorDetails for more information.",
                    status_code=400,
                    details={
                        "status_code": 400,
                        "error": {
                            "errorDetailType": "com.linkedin.common.error.BadRequest",
                            "errorDetails": {
                                "inputErrors": [
                                    {"code": "QUERY_PARAM_NOT_ALLOWED", "input": {"inputPath": {"fieldPath": "sortBy.field"}}},
                                    {"code": "QUERY_PARAM_NOT_ALLOWED", "input": {"inputPath": {"fieldPath": "sortBy.order"}}},
                                ]
                            },
                            "message": "Multiple errors occurred during param validation. Please see errorDetails for more information.",
                            "status": 400,
                        },
                    },
                )
            if "pivot.value=" in path or "timeGranularity.value=" in path:
                raise LinkedInValidationError(
                    "Multiple errors occurred during param validation. Please see errorDetails for more information.",
                    status_code=400,
                    details={
                        "status_code": 400,
                        "error": {
                            "errorDetailType": "com.linkedin.common.error.BadRequest",
                            "errorDetails": {
                                "inputErrors": [
                                    {"code": "QUERY_PARAM_NOT_ALLOWED", "input": {"inputPath": {"fieldPath": "pivot.value"}}},
                                    {
                                        "code": "QUERY_PARAM_NOT_ALLOWED",
                                        "input": {"inputPath": {"fieldPath": "timeGranularity.value"}},
                                    },
                                ]
                            },
                            "message": "Multiple errors occurred during param validation. Please see errorDetails for more information.",
                            "status": 400,
                        },
                    },
                )
            return {"elements": [{"impressions": 1}]}

    client = QueryParamNotAllowedFlakyClient(calls=[])

    result = get_insights(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "pivot": "campaign",
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "time_granularity": "MONTHLY",
            "fields": ["impressions", "clicks", "costInLocalCurrency"],
            "sort_by_field": "COST_IN_LOCAL_CURRENCY",
            "sort_order": "DESCENDING",
        },
    )

    assert result["ok"] is True
    called_paths = [path for path, _ in client.calls]
    assert len(called_paths) == 6
    assert "pivot=CAMPAIGN" in called_paths[-1]
    assert "timeGranularity=MONTHLY" in called_paths[-1]
    assert "sortBy.field=" not in called_paths[-1]
    assert "sortBy.order=" not in called_paths[-1]


def test_get_insights_rejects_more_than_20_fields(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])
    fields = [
        "actionClicks",
        "adUnitClicks",
        "approximateMemberReach",
        "averageDwellTime",
        "audiencePenetration",
        "cardClicks",
        "cardImpressions",
        "clicks",
        "commentLikes",
        "comments",
        "companyPageClicks",
        "conversionValueInLocalCurrency",
        "costInLocalCurrency",
        "costInUsd",
        "costPerQualifiedLead",
        "dateRange",
        "documentCompletions",
        "documentFirstQuartileCompletions",
        "documentMidpointCompletions",
        "documentThirdQuartileCompletions",
        "downloadClicks",
    ]

    with pytest.raises(ValueError, match="at most 20"):
        get_insights(
            client=client,
            settings=settings,
            arguments={"pivot": "campaign", "fields": fields},
        )


def test_list_account_intelligence_builds_filter_criteria_query(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_account_intelligence(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "lookback_window": "LAST_30_DAYS",
            "ad_segment_ids": ["123", "urn:li:adSegment:456"],
            "campaign_id": "469031486",
            "skip_company_decoration": True,
            "page_size": 500,
            "page_start": 0,
        },
    )

    assert result["ok"] is True
    path, params = client.calls[0]
    assert path.startswith("accountIntelligence?")
    assert "q=account" in path
    assert "account=urn%3Ali%3AsponsoredAccount%3A508834004" in path
    assert "start=0" in path
    assert "count=500" in path
    assert "skipCompanyDecoration=true" in path
    assert (
        "filterCriteria=(lookbackWindow%3ALAST_30_DAYS,adSegments%3AList(urn%3Ali%3AadSegment%3A123,urn%3Ali%3AadSegment%3A456),campaign%3Aurn%3Ali%3AsponsoredCampaign%3A469031486)"
        in path
    )
    assert params == {}


def test_get_creative_rejects_invalid_id(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="sponsoredCreative"):
        get_creative(client=client, settings=settings, arguments={"id": "../bad"})


def test_list_creatives_preserves_restli_delimiters_for_creatives_filter(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = list_creatives(
        client=client,
        settings=settings,
        arguments={
            "ad_account_id": "508834004",
            "creative_ids": ["935973186", "892320746", "892350816", "935963196"],
            "fields": ["id", "name", "campaign", "content"],
        },
    )

    assert result["ok"] is True
    path, params = client.calls[0]
    assert path.startswith("adAccounts/508834004/creatives?")
    assert "q=criteria" in path
    assert (
        "creatives=List(urn%3Ali%3AsponsoredCreative%3A935973186,urn%3Ali%3AsponsoredCreative%3A892320746,urn%3Ali%3AsponsoredCreative%3A892350816,urn%3Ali%3AsponsoredCreative%3A935963196)"
        in path
    )
    assert "%2C" not in path
    assert params == {}


def test_get_creative_uses_entity_endpoint_with_encoded_urn(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    result = get_creative(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "id": "935973186", "fields": ["id", "name", "campaign"]},
    )

    assert result["ok"] is True
    path, params = client.calls[0]
    assert path == "adAccounts/508834004/creatives/urn%3Ali%3AsponsoredCreative%3A935973186"
    assert params == {}
    assert result["data"] == {
        "id": "urn:li:sponsoredCreative:935973186",
        "name": "Creative",
        "campaign": "urn:li:sponsoredCampaign:469031486",
    }


def test_get_creative_supports_optional_image_url_field(settings: LinkedInAdsSettings) -> None:
    class CreativeImageClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if "/creatives/" in path:
                return {
                    "id": "urn:li:sponsoredCreative:935973186",
                    "name": "Creative",
                    "content": {
                        "contentEntities": [
                            {
                                "thumbnails": [
                                    {
                                        "resolvedUrl": "https://media.licdn.com/dms/image/C4D12AQF/test-image.jpg"
                                    }
                                ]
                            }
                        ]
                    },
                }
            return super().get_json(path, params)

    client = CreativeImageClient(calls=[])

    result = get_creative(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "id": "935973186", "fields": ["id", "name", "imageUrl"]},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "id": "urn:li:sponsoredCreative:935973186",
        "name": "Creative",
        "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/test-image.jpg",
    }
    called_paths = [path for path, _ in client.calls]
    assert not any(path.startswith("shares/") or path.startswith("posts/") for path in called_paths)


def test_get_creative_resolves_image_url_from_share_reference(settings: LinkedInAdsSettings) -> None:
    class ShareReferenceClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if "/creatives/" in path:
                return {
                    "id": "urn:li:sponsoredCreative:935973186",
                    "content": {"reference": "urn:li:share:123"},
                }
            if path == "posts/urn%3Ali%3Ashare%3A123":
                return {
                    "content": {
                        "contentEntities": [
                            {
                                "thumbnails": [
                                    {"resolvedUrl": "https://media.licdn.com/dms/image/C4D12AQF/from-share.png"}
                                ]
                            }
                        ]
                    }
                }
            return super().get_json(path, params)

    client = ShareReferenceClient(calls=[])

    result = get_creative(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "id": "935973186", "fields": ["id", "imageUrl"]},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "id": "urn:li:sponsoredCreative:935973186",
        "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/from-share.png",
    }
    assert any(path == "posts/urn%3Ali%3Ashare%3A123" for path, _ in client.calls)


def test_get_creative_resolves_image_url_from_ad_direct_sponsored_content_reference(
    settings: LinkedInAdsSettings,
) -> None:
    class DirectSponsoredContentClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if "/creatives/" in path:
                return {
                    "id": "urn:li:sponsoredCreative:935973186",
                    "content": {"reference": "urn:li:adDirectSponsoredContent:123"},
                }
            if path == "adDirectSponsoredContents/urn%3Ali%3AadDirectSponsoredContent%3A123":
                return {
                    "content": {
                        "contentEntities": [
                            {
                                "thumbnails": [
                                    {"resolvedUrl": "https://media.licdn.com/dms/image/C4D12AQF/from-dsc.jpeg"}
                                ]
                            }
                        ]
                    }
                }
            return super().get_json(path, params)

    client = DirectSponsoredContentClient(calls=[])

    result = get_creative(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "id": "935973186", "fields": ["id", "imageUrl"]},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "id": "urn:li:sponsoredCreative:935973186",
        "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/from-dsc.jpeg",
    }
    assert any(
        path == "adDirectSponsoredContents/urn%3Ali%3AadDirectSponsoredContent%3A123" for path, _ in client.calls
    )


def test_list_creatives_resolves_image_url_from_ad_direct_sponsored_content_reference(
    settings: LinkedInAdsSettings,
) -> None:
    class ListDirectSponsoredContentClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path.startswith("adAccounts/508834004/creatives?"):
                return {
                    "elements": [
                        {
                            "id": "urn:li:sponsoredCreative:935973186",
                            "content": {"reference": "urn:li:adDirectSponsoredContent:123"},
                        },
                        {
                            "id": "urn:li:sponsoredCreative:935973187",
                            "content": {"reference": "urn:li:adDirectSponsoredContent:123"},
                        },
                    ]
                }
            if path == "adDirectSponsoredContents/urn%3Ali%3AadDirectSponsoredContent%3A123":
                return {"media": {"url": "https://media.licdn.com/dms/image/C4D12AQF/list-dsc.png"}}
            return super().get_json(path, params)

    client = ListDirectSponsoredContentClient(calls=[])

    result = list_creatives(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "fields": ["id", "imageUrl"]},
    )

    assert result["ok"] is True
    assert result["data"] == [
        {
            "id": "urn:li:sponsoredCreative:935973186",
            "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/list-dsc.png",
        },
        {
            "id": "urn:li:sponsoredCreative:935973187",
            "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/list-dsc.png",
        },
    ]
    assert (
        len(
            [
                path
                for path, _ in client.calls
                if path == "adDirectSponsoredContents/urn%3Ali%3AadDirectSponsoredContent%3A123"
            ]
        )
        == 1
    )


def test_list_creatives_supports_optional_image_url_field(settings: LinkedInAdsSettings) -> None:
    class ListCreativeImageClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path.startswith("adAccounts/508834004/creatives?"):
                return {
                    "elements": [
                        {
                            "id": "urn:li:sponsoredCreative:935973186",
                            "content": {
                                "contentEntities": [
                                    {
                                        "thumbnails": [
                                            {
                                                "resolvedUrl": "https://media.licdn.com/dms/image/C4D12AQF/list-image.webp"
                                            }
                                        ]
                                    }
                                ]
                            },
                        }
                    ]
                }
            return super().get_json(path, params)

    client = ListCreativeImageClient(calls=[])

    result = list_creatives(
        client=client,
        settings=settings,
        arguments={"ad_account_id": "508834004", "fields": ["id", "imageUrl"]},
    )

    assert result["ok"] is True
    assert result["data"] == [
        {
            "id": "urn:li:sponsoredCreative:935973186",
            "imageUrl": "https://media.licdn.com/dms/image/C4D12AQF/list-image.webp",
        }
    ]


def test_get_share_content_extracts_image_url(settings: LinkedInAdsSettings) -> None:
    class ShareContentClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "posts/urn%3Ali%3Ashare%3A7379073146093568000":
                return {
                    "id": "urn:li:share:7379073146093568000",
                    "commentary": {"text": "Creative post text"},
                    "content": {
                        "contentEntities": [
                            {
                                "thumbnails": [
                                    {"resolvedUrl": "https://media.licdn.com/dms/image/D5603AQH/share-thumb.jpg"}
                                ],
                                "landingPageUrl": "https://example.com",
                            }
                        ]
                    },
                }
            return super().get_json(path, params)

    client = ShareContentClient(calls=[])

    result = get_share_content(
        client=client,
        settings=settings,
        arguments={"share_urn": "urn:li:share:7379073146093568000"},
    )

    assert result["ok"] is True
    assert result["data"] == {
        "share_urn": "urn:li:share:7379073146093568000",
        "source_endpoint": "posts",
        "post_url": "https://www.linkedin.com/feed/update/urn:li:share:7379073146093568000",
        "text": "Creative post text",
        "image_url": "https://media.licdn.com/dms/image/D5603AQH/share-thumb.jpg",
        "image_urls": ["https://media.licdn.com/dms/image/D5603AQH/share-thumb.jpg"],
        "thumbnail_urls": ["https://media.licdn.com/dms/image/D5603AQH/share-thumb.jpg"],
    }


def test_get_share_content_uses_posts_without_retired_shares(settings: LinkedInAdsSettings) -> None:
    class PostsClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            assert path == "posts/urn%3Ali%3Ashare%3A7379073146093568000"
            return {
                "id": "urn:li:share:7379073146093568000",
                "commentary": "Modern post text",
                "content": {"media": {"url": "https://media.licdn.com/dms/image/post.png"}},
            }

    client = PostsClient(calls=[])
    result = get_share_content(
        client=client, settings=settings,
        arguments={"share_urn": "urn:li:share:7379073146093568000"},
    )
    assert result["data"]["source_endpoint"] == "posts"
    assert result["data"]["text"] == "Modern post text"
    assert result["data"]["image_url"] == "https://media.licdn.com/dms/image/post.png"
    assert len(client.calls) == 1


def test_get_share_content_include_raw_payload(settings: LinkedInAdsSettings) -> None:
    class ShareRawClient(DummyClient):
        def get_json(self, path: str, params: dict | None) -> dict:
            self.calls.append((path, dict(params or {})))
            if path == "posts/urn%3Ali%3Ashare%3A7379073146093568000":
                return {"id": "urn:li:share:7379073146093568000", "commentary": {"text": "Raw text"}}
            return super().get_json(path, params)

    client = ShareRawClient(calls=[])

    result = get_share_content(
        client=client,
        settings=settings,
        arguments={"share_urn": "urn:li:share:7379073146093568000", "include_raw": True},
    )

    assert result["ok"] is True
    assert result["data"]["raw"] == {
        "id": "urn:li:share:7379073146093568000",
        "commentary": {"text": "Raw text"},
    }


def test_get_share_content_rejects_invalid_share_urn(settings: LinkedInAdsSettings) -> None:
    client = DummyClient(calls=[])

    with pytest.raises(ValueError, match="share URN"):
        get_share_content(
            client=client,
            settings=settings,
            arguments={"share_urn": "urn:li:sponsoredCreative:123"},
        )
