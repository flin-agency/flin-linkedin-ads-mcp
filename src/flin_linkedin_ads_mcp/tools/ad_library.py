"""Public transparency searches; no ad-account access or discovery is needed."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from ..config import LinkedInAdsSettings
from ..errors import LinkedInPermissionError
from ..linkedin_client import LinkedInClient
from .common import build_ok_response, date_range_to_restli, validate_date

TARGETING_CATEGORIES = (
    "LANGUAGE", "LOCATION", "AUDIENCE", "AGE", "GENDER", "COMPANY", "EDUCATION", "JOB",
    "INTERESTS_AND_TRAITS",
)
PARTNERSHIP_DATE_RANGES = ("PAST_24H", "PAST_WEEK", "PAST_MONTH")


def search_ad_library(
    *, client: LinkedInClient, settings: LinkedInAdsSettings, arguments: dict[str, Any],
) -> dict[str, Any]:
    params = {"q": "criteria"}
    for argument, parameter in (
        ("keyword", "keyword"), ("advertiser", "advertiser"), ("payer_name", "payerName"),
    ):
        if argument in arguments:
            params[parameter] = quote(_text(arguments[argument], argument), safe="")

    if "countries" in arguments:
        countries = arguments["countries"]
        if not isinstance(countries, list) or not countries:
            raise ValueError("countries must be a non-empty array of two-letter country codes")
        urns = []
        for country in countries:
            if not isinstance(country, str) or not re.fullmatch(r"[A-Za-z]{2}", country):
                raise ValueError("countries must contain two-letter country codes, e.g. CH or DE")
            urns.append(quote(f"urn:li:country:{country.lower()}", safe=""))
        params["countries"] = f"(value:List({','.join(dict.fromkeys(urns))}))"

    if "date_from" in arguments or "date_to" in arguments:
        if "date_from" not in arguments or "date_to" not in arguments:
            raise ValueError("date_from and date_to must be provided together (end is exclusive)")
        start = validate_date(arguments["date_from"], parameter_name="date_from")
        end = validate_date(arguments["date_to"], parameter_name="date_to")
        if start >= end:
            raise ValueError("date_from must be before date_to (end is exclusive)")
        params["dateRange"] = date_range_to_restli(date_from=start, date_to=end)

    for argument, parameter in (
        ("included_targeting_categories", "includedTargetingFacetCategories"),
        ("excluded_targeting_categories", "excludedTargetingFacetCategories"),
    ):
        if argument in arguments:
            values = arguments[argument]
            if not isinstance(values, list) or not values:
                raise ValueError(f"{argument} must be a non-empty array")
            if any(not isinstance(v, str) or v not in TARGETING_CATEGORIES for v in values):
                raise ValueError(f"{argument} contains an unsupported targeting category")
            params[parameter] = f"List({','.join(dict.fromkeys(values))})"

    if "impressions_from" in arguments or "impressions_to" in arguments:
        if "impressions_from" not in arguments or "impressions_to" not in arguments:
            raise ValueError("impressions_from and impressions_to must be provided together")
        lower = _integer(arguments["impressions_from"], "impressions_from", minimum=0)
        upper = _integer(arguments["impressions_to"], "impressions_to", minimum=0)
        if (upper == 0 and lower < 1_000_000) or (upper != 0 and upper <= lower):
            raise ValueError("impressions_to must exceed impressions_from; 0 is the open upper bound for 1M+")
        params["totalImpressionsRange"] = f"(from:{lower},to:{upper})"

    if "sort_order" in arguments:
        order = arguments["sort_order"]
        if order not in ("ASCENDING", "DESCENDING"):
            raise ValueError("sort_order must be ASCENDING or DESCENDING")
        params["sortBy"] = f"(order:{order},field:CREATED_TIME)"

    return _search(client, settings, "adLibrary", params, arguments)


def search_brand_partnerships(
    *, client: LinkedInClient, settings: LinkedInAdsSettings, arguments: dict[str, Any],
) -> dict[str, Any]:
    params = {
        "q": "searchCriteria",
        "keyword": quote(_text(arguments.get("keyword"), "keyword"), safe=""),
    }
    if "date_range" in arguments:
        date_range = arguments["date_range"]
        if date_range not in PARTNERSHIP_DATE_RANGES:
            raise ValueError("date_range must be PAST_24H, PAST_WEEK or PAST_MONTH")
        params["dateRange"] = date_range
    return _search(client, settings, "paidEndorsementPosts", params, arguments)


def _search(
    client: LinkedInClient, settings: LinkedInAdsSettings, endpoint: str,
    params: dict[str, str], arguments: dict[str, Any],
) -> dict[str, Any]:
    start = _integer(arguments.get("page_start", 0), "page_start", minimum=0)
    count = _integer(arguments.get("page_size", 25), "page_size", minimum=1, maximum=25)
    params.update(start=str(start), count=str(count))
    # Preserve Rest.li structure while escaping user text and URN values separately.
    query = "&".join(f"{key}={value}" for key, value in params.items())
    try:
        payload = client.get_json(f"{endpoint}?{query}", params={})
    except LinkedInPermissionError as exc:
        raise LinkedInPermissionError(
            "LinkedIn denied Ad Library access. Check that the app issuing this member token "
            "has the LinkedIn Ad Library product provisioned; no additional OAuth scope is needed.",
            status_code=exc.status_code, request_id=exc.request_id, details=exc.details,
        ) from exc
    data = payload.get("elements", [])
    if not isinstance(data, list):
        data = []
    paging = payload.get("paging", {})
    if not isinstance(paging, dict):
        paging = {}
    total = paging.get("total")
    total = total if type(total) is int and total >= 0 else None
    next_start = _next_start(paging, start=start, count=count, returned=len(data), total=total)
    result = build_ok_response(
        data=data, api_version=settings.api_version,
        request_id=getattr(client, "last_request_id", None),
        next_after=str(next_start) if next_start is not None else None,
        has_next=next_start is not None,
    )
    result["paging"].update(start=start, count=count, total=total, next_start=next_start)
    return result


def _next_start(
    paging: dict[str, Any], *, start: int, count: int, returned: int, total: int | None,
) -> int | None:
    if not returned:
        return None
    links = paging.get("links", [])
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict) or link.get("rel") != "next":
                continue
            href = link.get("href")
            if not isinstance(href, str):
                continue
            try:
                offset = parse_qs(urlsplit(href).query).get("start", [""])[0]
                if re.fullmatch(r"[0-9]+", offset) and int(offset) > start:
                    return int(offset)
            except ValueError:
                continue
    # Never follow server-provided URLs. Return only an offset for the same tool/filters.
    next_start = start + returned
    if total is not None:
        return next_start if next_start < total else None
    # Some responses omit paging entirely. A full page may require one final empty fetch.
    return next_start if returned >= count else None


def _integer(value: Any, name: str, *, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} must be an integer >= {minimum}" + (
            f" and <= {maximum}" if maximum is not None else ""
        ))
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()
