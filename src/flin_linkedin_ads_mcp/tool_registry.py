from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .tools.ad_library import PARTNERSHIP_DATE_RANGES, TARGETING_CATEGORIES


ACCOUNT_ID_PATTERN = "^(urn:li:sponsoredAccount:)?[0-9]+$"
CAMPAIGN_GROUP_PATTERN = "^(urn:li:sponsoredCampaignGroup:)?[0-9]+$"
CAMPAIGN_PATTERN = "^(urn:li:sponsoredCampaign:)?[0-9]+$"
CREATIVE_PATTERN = "^(urn:li:sponsoredCreative:)?[0-9]+$"
AD_SEGMENT_PATTERN = "^(urn:li:adSegment:)?[0-9]+$"
SHARE_URN_PATTERN = "^urn:li:share:[0-9]+$"
ORGANIZATION_URN_PATTERN = "^urn:li:organization:[0-9]+$"
FIELD_PATTERN = "^[A-Za-z][A-Za-z0-9_.]*$"
DATE_PATTERN = "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="linkedin_login",
            description=(
                "Connect or reconnect LinkedIn Ads, including after EXPIRED_ACCESS_TOKEN/401. "
                "Returns a login URL to open in a browser on the MCP server's computer. "
                "Saves credentials locally after consent. Requires configured LinkedIn app "
                "client ID and secret. Never ask for tokens, passwords or secrets in chat."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="linkedin_login_status",
            description=(
                "Check local LinkedIn login progress and token expiry without exposing credentials. "
                "After login, use list_ad_accounts to verify API access."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="list_ad_accounts",
            description="List LinkedIn ad accounts accessible by the token",
            input_schema=_list_schema(),
        ),
        ToolSpec(
            name="get_ad_account",
            description="Fetch one LinkedIn ad account by id",
            input_schema=_account_id_schema(),
        ),
        ToolSpec(
            name="list_campaign_groups",
            description="List campaign groups for an ad account",
            input_schema=_account_list_schema(),
        ),
        ToolSpec(
            name="get_campaign_group",
            description="Fetch one campaign group by id",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CAMPAIGN_GROUP_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_campaigns",
            description="List campaigns for an ad account",
            input_schema=_account_list_schema(),
        ),
        ToolSpec(
            name="get_campaign",
            description="Fetch one campaign by id",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CAMPAIGN_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_creatives",
            description=(
                "List creatives for an ad account. Optional fields imageUrl and metadata use "
                "one extra GET per creative on API 202610+. Image URLs are external and may expire; "
                "restricted dashboards need approved embedded/local assets."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "campaign_id": {"type": "string", "pattern": CAMPAIGN_PATTERN},
                    "creative_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": CREATIVE_PATTERN},
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "page_token": {"type": "string"},
                    "sort_order": {"type": "string", "enum": ["ASCENDING", "DESCENDING"]},
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_creative",
            description=(
                "Fetch one creative by id. Request fields imageUrl or metadata for the visual "
                "asset URL via CreativeMetadata on API 202610+, without needing Posts access. "
                "Image URLs are external and may expire."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "id": {"type": "string", "pattern": CREATIVE_PATTERN},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "required": ["id"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_share_content",
            description=(
                "Resolve LinkedIn share/ugcPost content via the Posts and Images APIs. Requires "
                "their additional permissions. For ad images prefer get_creative with imageUrl "
                "on API 202610+. External image URLs alone cannot bypass dashboard restrictions."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "share_urn": {"type": "string", "pattern": "^urn:li:(share|ugcPost):[0-9]+$"},
                    "include_raw": {"type": "boolean"},
                },
                "required": ["share_urn"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="get_insights",
            description="Fetch LinkedIn ads analytics",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "pivot": {
                        "type": "string",
                        "enum": [
                            "company",
                            "share",
                            "campaign",
                            "campaign_group",
                            "account",
                            "creative",
                            "conversion",
                            "conversation_node",
                            "conversation_node_option_index",
                            "serving_location",
                            "card_index",
                            "member_company_size",
                            "member_industry",
                            "member_seniority",
                            "member_job_title",
                            "member_job_function",
                            "member_country_v2",
                            "member_region_v2",
                            "member_company",
                            "member_county",
                            "placement_name",
                            "impression_device_type",
                            "event_stage",
                        ],
                        "default": "campaign",
                    },
                    "entity_ids": {"type": "array", "items": {"type": "string"}},
                    "account_ids": {"type": "array", "items": {"type": "string", "pattern": ACCOUNT_ID_PATTERN}},
                    "campaign_group_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": CAMPAIGN_GROUP_PATTERN},
                    },
                    "campaign_ids": {"type": "array", "items": {"type": "string", "pattern": CAMPAIGN_PATTERN}},
                    "creative_ids": {"type": "array", "items": {"type": "string", "pattern": CREATIVE_PATTERN}},
                    "share_ids": {"type": "array", "items": {"type": "string", "pattern": SHARE_URN_PATTERN}},
                    "company_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": ORGANIZATION_URN_PATTERN},
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                    "time_granularity": {"type": "string", "enum": ["DAILY", "MONTHLY", "ALL", "YEARLY"], "default": "DAILY"},
                    "date_from": {"type": "string", "pattern": DATE_PATTERN},
                    "date_to": {"type": "string", "pattern": DATE_PATTERN},
                    "campaign_type": {
                        "type": "string",
                        "enum": ["TEXT_AD", "SPONSORED_UPDATES", "SPONSORED_INMAILS", "DYNAMIC"],
                    },
                    "objective_type": {
                        "type": "string",
                        "enum": [
                            "LEAD_GENERATION",
                            "CREATIVE_ENGAGEMENT",
                            "WEBSITE_TRAFFIC",
                            "VIDEO_VIEW",
                            "BRAND_AWARENESS",
                            "WEBSITE_CONVERSION",
                            "WEBSITE_VISIT",
                            "ENGAGEMENT",
                            "JOB_APPLICANT",
                        ],
                    },
                    "sort_by_field": {
                        "type": "string",
                        "enum": [
                            "COST_IN_LOCAL_CURRENCY",
                            "IMPRESSIONS",
                            "CLICKS",
                            "ONE_CLICK_LEADS",
                            "OPENS",
                            "SENDS",
                            "EXTERNAL_WEBSITE_CONVERSIONS",
                        ],
                    },
                    "sort_order": {"type": "string", "enum": ["ASCENDING", "DESCENDING"]},
                },
                "required": ["date_from"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="list_account_intelligence",
            description="List company-level account intelligence rows (private LinkedIn API access required)",
            input_schema={
                "type": "object",
                "properties": {
                    "ad_account_id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
                    "lookback_window": {
                        "type": "string",
                        "enum": ["LAST_7_DAYS", "LAST_30_DAYS", "LAST_60_DAYS", "LAST_90_DAYS"],
                        "default": "LAST_90_DAYS",
                    },
                    "ad_segment_ids": {
                        "type": "array",
                        "items": {"type": "string", "pattern": AD_SEGMENT_PATTERN},
                    },
                    "campaign_id": {"type": "string", "pattern": CAMPAIGN_PATTERN},
                    "skip_company_decoration": {"type": "boolean"},
                    "page_start": {"type": "integer", "minimum": 0},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "fields": {
                        "type": "array",
                        "items": {"type": "string", "pattern": FIELD_PATTERN},
                    },
                },
                "additionalProperties": False,
            },
        ),
    ] + _ad_library_specs()


def _ad_library_specs() -> list[ToolSpec]:
    pagination = {
        "page_start": {
            "type": "integer", "minimum": 0, "default": 0,
            "description": "Offset; use paging.next_start for the next page with the same filters.",
        },
        "page_size": {"type": "integer", "minimum": 1, "maximum": 25, "default": 25},
    }
    text = {"type": "string", "minLength": 1}
    targeting = {
        "type": "array", "minItems": 1,
        "items": {"type": "string", "enum": list(TARGETING_CATEGORIES)},
    }
    return [
        ToolSpec(
            name="search_ad_library",
            description=(
                "Search public LinkedIn ads, including other advertisers, by keyword, advertiser, "
                "payer, country, dates, targeting categories and impression range. No ad account "
                "required. Requires the LinkedIn Ad Library product on the token's app, with no "
                "extra OAuth scope. Returns preview URLs and available transparency details; "
                "no ad copy/media download, clicks or spend. Targeting/impression details depend "
                "on availability (particularly EU ads). Without dates LinkedIn searches only "
                "today-2 to today-1. date_to is exclusive. Multiple keywords use AND."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": dict(text), "advertiser": dict(text), "payer_name": dict(text),
                    "countries": {
                        "type": "array", "minItems": 1,
                        "items": {"type": "string", "pattern": "^[A-Za-z]{2}$"},
                        "description": "ISO two-letter country codes, e.g. CH, DE, AT.",
                    },
                    "date_from": {
                        "type": "string", "pattern": DATE_PATTERN,
                        "description": "Inclusive start; requires date_to.",
                    },
                    "date_to": {
                        "type": "string", "pattern": DATE_PATTERN,
                        "description": "Exclusive end; requires date_from.",
                    },
                    "included_targeting_categories": dict(targeting),
                    "excluded_targeting_categories": dict(targeting),
                    "impressions_from": {"type": "integer", "minimum": 0},
                    "impressions_to": {
                        "type": "integer", "minimum": 0,
                        "description": "Requires impressions_from. Use 0 for an open upper bound (1M+).",
                    },
                    "sort_order": {
                        "type": "string", "enum": ["ASCENDING", "DESCENDING"],
                        "description": "Sort by ad creation time; LinkedIn defaults to DESCENDING.",
                    },
                    **pagination,
                },
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="search_brand_partnerships",
            description=(
                "Search organic LinkedIn posts declared by creators as brand partnerships. "
                "Returns post URLs. Requires the LinkedIn Ad Library product, no extra OAuth "
                "scope or ad account. Multiple keywords use AND. Without date_range searches "
                "available posts up to one year old."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "keyword": dict(text),
                    "date_range": {"type": "string", "enum": list(PARTNERSHIP_DATE_RANGES)},
                    **pagination,
                },
                "required": ["keyword"],
                "additionalProperties": False,
            },
        ),
    ]


def _list_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {"type": "string", "pattern": FIELD_PATTERN},
            },
            "search": {"type": "string"},
            "page_size": {"type": "integer", "minimum": 1, "maximum": 1000},
            "page_token": {"type": "string"},
            "sort_order": {"type": "string", "enum": ["ASCENDING", "DESCENDING"]},
            "test": {"type": "boolean"},
        },
        "additionalProperties": False,
    }


def _account_id_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string", "pattern": ACCOUNT_ID_PATTERN},
            "fields": {
                "type": "array",
                "items": {"type": "string", "pattern": FIELD_PATTERN},
            },
        },
        "required": ["id"],
        "additionalProperties": False,
    }


def _account_list_schema() -> dict[str, Any]:
    schema = _list_schema()
    schema["properties"]["ad_account_id"] = {"type": "string", "pattern": ACCOUNT_ID_PATTERN}
    return schema
