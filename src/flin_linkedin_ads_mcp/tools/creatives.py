from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from ..config import LinkedInAdsSettings
from ..errors import LinkedInAdsError
from ..linkedin_client import LinkedInClient
from .common import (
    build_collection_response,
    build_entity_response,
    compact_params,
    normalize_campaign_id,
    normalize_creative_urn,
    normalize_page_size,
    normalize_sort_order,
    resolve_ad_account_id,
    resolve_fields,
    to_campaign_urn,
    to_restli_list,
)

DEFAULT_CREATIVE_FIELDS = ["id", "name", "intendedStatus", "campaign", "account", "isServing"]
ALLOWED_CREATIVE_FIELDS = {
    "id",
    "name",
    "intendedStatus",
    "campaign",
    "account",
    "isServing",
    "isTest",
    "content",
    "review",
    "servingHoldReasons",
    "createdAt",
    "createdBy",
    "lastModifiedAt",
    "lastModifiedBy",
    "leadgenCallToAction",
}
DERIVED_CREATIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "imageUrl": ("content",),
}


def list_creatives(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    requested_fields, output_fields_csv, derived_fields = _prepare_requested_fields(arguments.get("fields"))
    fields_csv = resolve_fields(
        requested_fields,
        default_fields=DEFAULT_CREATIVE_FIELDS,
        allowed_fields=ALLOWED_CREATIVE_FIELDS,
    )

    creative_ids = arguments.get("creative_ids")
    if creative_ids is not None and not isinstance(creative_ids, list):
        raise ValueError("creative_ids must be an array")

    campaign_id = arguments.get("campaign_id")
    campaign_selector = None
    if campaign_id is not None:
        campaign_selector = to_restli_list([to_campaign_urn(normalize_campaign_id(campaign_id, parameter_name="campaign_id"))])

    creative_selector = None
    if isinstance(creative_ids, list) and creative_ids:
        creative_selector = to_restli_list(
            [normalize_creative_urn(creative_id, parameter_name="creative_ids[]") for creative_id in creative_ids]
        )

    params = compact_params(
        {
            "q": "criteria",
            "campaigns": campaign_selector,
            "creatives": creative_selector,
            "pageSize": normalize_page_size(arguments.get("page_size")),
            "pageToken": arguments.get("page_token"),
            "sortOrder": normalize_sort_order(arguments.get("sort_order")),
        }
    )

    payload = client.get_json(
        f"adAccounts/{account_id}/creatives?{_raw_query(params)}",
        params={},
    )
    if "imageUrl" in derived_fields:
        payload = _inject_derived_image_url_in_collection(payload=payload, client=client)

    response_fields_csv = output_fields_csv if output_fields_csv is not None else fields_csv
    return build_collection_response(
        payload=payload,
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=response_fields_csv,
    )


def get_creative(
    *,
    client: LinkedInClient,
    settings: LinkedInAdsSettings,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    account_id = resolve_ad_account_id(client=client, ad_account_id=arguments.get("ad_account_id"))
    creative_urn = normalize_creative_urn(arguments["id"], parameter_name="id")
    creative_path = quote(creative_urn, safe="")
    requested_fields, output_fields_csv, derived_fields = _prepare_requested_fields(arguments.get("fields"))
    fields_csv = resolve_fields(
        requested_fields,
        default_fields=DEFAULT_CREATIVE_FIELDS,
        allowed_fields=ALLOWED_CREATIVE_FIELDS,
    )

    payload = client.get_json(
        f"adAccounts/{account_id}/creatives/{creative_path}",
        params={},
    )
    if "imageUrl" in derived_fields and isinstance(payload, Mapping):
        payload = _inject_derived_image_url_in_entity(payload=payload, client=client)

    response_fields_csv = output_fields_csv if output_fields_csv is not None else fields_csv

    return build_entity_response(
        payload=payload if isinstance(payload, dict) else {},
        api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        fields_csv=response_fields_csv,
    )


def _raw_query(params: dict[str, Any]) -> str:
    segments = [f"{quote(str(key), safe='._')}={quote(_query_value(value), safe=',()')}" for key, value in params.items()]
    return "&".join(segments)


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _prepare_requested_fields(value: Any) -> tuple[Any, str | None, set[str]]:
    if not isinstance(value, list):
        return value, None, set()

    api_fields: list[Any] = []
    output_fields: list[str] = []
    derived_fields: set[str] = set()
    seen_api_fields: set[str] = set()
    seen_output_fields: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            api_fields.append(item)
            continue

        clean_item = item.strip()
        if clean_item not in seen_output_fields:
            seen_output_fields.add(clean_item)
            output_fields.append(clean_item)

        dependencies = DERIVED_CREATIVE_FIELDS.get(clean_item)
        if dependencies is None:
            if clean_item not in seen_api_fields:
                seen_api_fields.add(clean_item)
                api_fields.append(clean_item)
            continue

        derived_fields.add(clean_item)
        for dependency in dependencies:
            if dependency in seen_api_fields:
                continue
            seen_api_fields.add(dependency)
            api_fields.append(dependency)

    output_fields_csv = ",".join(output_fields) if output_fields else None
    return api_fields, output_fields_csv, derived_fields


def _inject_derived_image_url_in_collection(*, payload: dict[str, Any], client: LinkedInClient) -> dict[str, Any]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        return payload

    content_reference_cache: dict[str, str | None] = {}
    normalized_elements: list[Any] = []
    for item in elements:
        if not isinstance(item, Mapping):
            normalized_elements.append(item)
            continue

        row = dict(item)
        row["imageUrl"] = _resolve_image_url_for_creative(
            creative=row,
            client=client,
            content_reference_cache=content_reference_cache,
        )
        normalized_elements.append(row)

    payload["elements"] = normalized_elements
    return payload


def _inject_derived_image_url_in_entity(*, payload: Mapping[str, Any], client: LinkedInClient) -> dict[str, Any]:
    row = dict(payload)
    row["imageUrl"] = _resolve_image_url_for_creative(
        creative=row,
        client=client,
        content_reference_cache={},
    )
    return row


def _resolve_image_url_for_creative(
    *,
    creative: Mapping[str, Any],
    client: LinkedInClient,
    content_reference_cache: dict[str, str | None],
) -> str | None:
    direct_url = _find_image_url(creative.get("content"))
    if direct_url:
        return direct_url

    content_reference = _extract_content_reference(creative.get("content"))
    if not content_reference:
        return None

    if content_reference in content_reference_cache:
        return content_reference_cache[content_reference]

    resolved_url = _resolve_image_url_from_content_reference(client=client, content_reference=content_reference)
    content_reference_cache[content_reference] = resolved_url
    return resolved_url


def _extract_content_reference(content: Any) -> str | None:
    if not isinstance(content, Mapping):
        return None
    reference = content.get("reference")
    if not isinstance(reference, str):
        return None
    clean_reference = reference.strip()
    if not clean_reference.startswith("urn:li:"):
        return None
    return clean_reference


def _resolve_image_url_from_content_reference(*, client: LinkedInClient, content_reference: str) -> str | None:
    if content_reference.startswith("urn:li:share:"):
        return _resolve_image_url_from_share_reference(client=client, share_reference=content_reference)
    if content_reference.startswith("urn:li:adDirectSponsoredContent:"):
        return _resolve_image_url_from_ad_direct_sponsored_content_reference(
            client=client,
            sponsored_content_reference=content_reference,
        )
    return None


def _resolve_image_url_from_share_reference(*, client: LinkedInClient, share_reference: str) -> str | None:
    share_path = quote(share_reference, safe="")
    for path in (f"shares/{share_path}", f"posts/{share_path}"):
        try:
            payload = client.get_json(path, params={})
        except LinkedInAdsError:
            continue
        image_url = _find_image_url(payload)
        if image_url:
            return image_url
    return None


def _resolve_image_url_from_ad_direct_sponsored_content_reference(
    *,
    client: LinkedInClient,
    sponsored_content_reference: str,
) -> str | None:
    sponsored_content_path = quote(sponsored_content_reference, safe="")
    try:
        payload = client.get_json(f"adDirectSponsoredContents/{sponsored_content_path}", params={})
    except LinkedInAdsError:
        return None

    return _find_image_url(payload)


def _find_image_url(value: Any) -> str | None:
    if isinstance(value, str):
        return value if _looks_like_image_url(value) else None

    if isinstance(value, Mapping):
        for key in ("imageUrl", "thumbnailUrl", "resolvedUrl", "url"):
            if key in value:
                image_url = _find_image_url(value.get(key))
                if image_url:
                    return image_url
        for nested_value in value.values():
            image_url = _find_image_url(nested_value)
            if image_url:
                return image_url
        return None

    if isinstance(value, list):
        for item in value:
            image_url = _find_image_url(item)
            if image_url:
                return image_url
        return None

    return None


def _looks_like_image_url(value: str) -> bool:
    clean_value = value.strip()
    if not clean_value:
        return False
    lower = clean_value.lower()
    if not lower.startswith(("https://", "http://")):
        return False
    without_query = lower.split("?", 1)[0]
    if without_query.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif", ".svg")):
        return True
    if "media.licdn.com" in lower:
        return True
    if "/dms/image/" in lower:
        return True
    return False
