from __future__ import annotations

from flin_linkedin_ads_mcp.tool_registry import tool_specs


def test_tool_registry_exposes_expected_read_only_tools() -> None:
    names = [spec.name for spec in tool_specs()]

    assert names == [
        "linkedin_login",
        "linkedin_login_status",
        "list_ad_accounts",
        "get_ad_account",
        "list_campaign_groups",
        "get_campaign_group",
        "list_campaigns",
        "get_campaign",
        "list_creatives",
        "get_creative",
        "get_creative_media",
        "get_share_content",
        "get_insights",
        "list_account_intelligence",
        "search_ad_library",
        "search_brand_partnerships",
    ]


def test_get_insights_exposes_pivot_field() -> None:
    spec = next(spec for spec in tool_specs() if spec.name == "get_insights")

    assert "pivot" in spec.input_schema["properties"]
