from __future__ import annotations

from typing import Any, Callable

from .config import LinkedInAdsSettings
from .guards import assert_read_only_tool
from .linkedin_client import LinkedInClient
from .tools.account_intelligence import list_account_intelligence
from .tools.accounts import get_ad_account, list_ad_accounts
from .tools.ad_library import search_ad_library, search_brand_partnerships
from .tools.campaign_groups import get_campaign_group, list_campaign_groups
from .tools.campaigns import get_campaign, list_campaigns
from .tools.creatives import get_creative, list_creatives
from .tools.insights import get_insights
from .tools.share_content import get_share_content
from .tools.media import MediaResult, get_creative_media

ToolHandler = Callable[[LinkedInClient, LinkedInAdsSettings, dict[str, Any]], dict[str, Any] | MediaResult]

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_creative_media": lambda client, settings, arguments: get_creative_media(
        client=client, settings=settings, arguments=arguments,
    ),
    "search_ad_library": lambda client, settings, arguments: search_ad_library(
        client=client, settings=settings, arguments=arguments,
    ),
    "search_brand_partnerships": lambda client, settings, arguments: search_brand_partnerships(
        client=client, settings=settings, arguments=arguments,
    ),
    "list_ad_accounts": lambda client, settings, arguments: list_ad_accounts(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_ad_account": lambda client, settings, arguments: get_ad_account(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_campaign_groups": lambda client, settings, arguments: list_campaign_groups(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_campaign_group": lambda client, settings, arguments: get_campaign_group(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_campaigns": lambda client, settings, arguments: list_campaigns(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_campaign": lambda client, settings, arguments: get_campaign(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_creatives": lambda client, settings, arguments: list_creatives(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_creative": lambda client, settings, arguments: get_creative(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_share_content": lambda client, settings, arguments: get_share_content(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "get_insights": lambda client, settings, arguments: get_insights(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
    "list_account_intelligence": lambda client, settings, arguments: list_account_intelligence(
        client=client,
        settings=settings,
        arguments=arguments,
    ),
}


def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    settings: LinkedInAdsSettings,
    client: LinkedInClient,
) -> dict[str, Any] | MediaResult:
    assert_read_only_tool(name)
    try:
        handler = TOOL_HANDLERS[name]
    except KeyError as exc:
        raise KeyError(f"Unknown tool: {name}") from exc
    return handler(client, settings, arguments)
