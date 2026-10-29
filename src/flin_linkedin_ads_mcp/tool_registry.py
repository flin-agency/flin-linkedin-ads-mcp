from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
            description="List creatives for an ad account",
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
            description="Fetch one creative by id",
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
            description="Resolve LinkedIn share content and image URLs by share URN",
            input_schema={
                "type": "object",
                "properties": {
                    "share_urn": {"type": "string", "pattern": SHARE_URN_PATTERN},
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
