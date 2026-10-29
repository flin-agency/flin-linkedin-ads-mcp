from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class LinkedInAdsSettings:
    access_token: str = field(repr=False)
    api_version: str
    restli_protocol_version: str
    timeout_seconds: float
    max_retries: int
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = "http://localhost:9876/callback"
    token_file: Path = field(
        default_factory=lambda: Path.home() / ".config/flin-linkedin-ads-mcp/tokens.json"
    )


def load_config(env: Mapping[str, str] | None = None) -> LinkedInAdsSettings:
    source = os.environ if env is None else env
    access_token = source.get("LINKEDIN_ACCESS_TOKEN", "")
    client_id = source.get("LINKEDIN_CLIENT_ID", "")
    client_secret = source.get("LINKEDIN_CLIENT_SECRET", "")
    if bool(client_id) != bool(client_secret):
        raise ValueError("Set both LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET for login")
    redirect_uri = source.get("LINKEDIN_REDIRECT_URI", "http://localhost:9876/callback")
    validate_redirect_uri(redirect_uri)

    return LinkedInAdsSettings(
        access_token=access_token,
        api_version=source.get("LINKEDIN_API_VERSION", "202603"),
        restli_protocol_version=source.get("LINKEDIN_RESTLI_PROTOCOL_VERSION", "2.0.0"),
        timeout_seconds=float(source.get("LINKEDIN_TIMEOUT_SECONDS", "30")),
        max_retries=int(source.get("LINKEDIN_MAX_RETRIES", "3")),
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        token_file=Path(source.get(
            "LINKEDIN_TOKEN_FILE", str(Path.home() / ".config/flin-linkedin-ads-mcp/tokens.json")
        )).expanduser(),
    )


def validate_redirect_uri(uri: str) -> None:
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or not parsed.port
        or not parsed.path.startswith("/")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "LINKEDIN_REDIRECT_URI must be an HTTP loopback URL with port and path, "
            "for example http://localhost:9876/callback"
        )
