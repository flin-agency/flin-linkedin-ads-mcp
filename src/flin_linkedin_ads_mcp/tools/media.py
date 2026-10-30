from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

import httpx

from ..config import LinkedInAdsSettings
from ..errors import LinkedInAPIError, LinkedInPermissionError, LinkedInValidationError
from ..linkedin_client import LinkedInClient
from .common import build_entity_response
from .creatives import get_creative, _extract_content_reference
from .share_content import _fetch_share_payload

IMAGE_LIMIT = 5 * 1024 * 1024
VIDEO_LIMIT = 100 * 1024 * 1024
EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "video/mp4": ".mp4",
}


@dataclass
class MediaResult:
    response: dict[str, Any]
    image: bytes | None = None


def get_creative_media(
    *, client: LinkedInClient, settings: LinkedInAdsSettings, arguments: dict[str, Any],
) -> MediaResult:
    """Fetch one authorized creative's media, never an arbitrary caller-supplied URL."""
    kind = arguments.get("kind", "preview")
    output = arguments.get("output", "both")
    if kind not in ("preview", "video"):
        raise ValueError("kind must be preview or video")
    if output not in ("inline", "file", "both"):
        raise ValueError("output must be inline, file or both")
    if kind == "video" and output == "inline":
        raise ValueError("Videos require output=file or both; inline images use kind=preview")
    fields = ["id", "content"]
    if kind == "preview":
        fields.append("imageUrl")
    if settings.api_version >= "202610":
        fields.append("metadata")
    creative = get_creative(client=client, settings=settings, arguments={
        "id": arguments["id"], "ad_account_id": arguments.get("ad_account_id"), "fields": fields,
    })["data"]
    expires_at = None
    if kind == "preview":
        url = creative.get("imageUrl")
    else:
        url, expires_at = _video_url(creative, client=client)
    if not isinstance(url, str) or not url:
        raise LinkedInValidationError(
            f"No {kind} download URL is available for this creative. "
            "The asset may be unavailable or require additional API permissions."
        )
    body, mime = _download(url, kind=kind, timeout=settings.timeout_seconds)
    digest = hashlib.sha256(body).hexdigest()
    data: dict[str, Any] = {
        "creative_id": creative["id"], "kind": kind, "mime_type": mime,
        "size_bytes": len(body), "sha256": digest, "download_url_expires_at": expires_at,
        "inline_image": output in ("inline", "both") and kind == "preview",
    }
    if output in ("file", "both"):
        path = _save(body, directory=settings.media_dir, filename=digest + EXTENSIONS[mime])
        data.update(local_path=str(path), file_uri=path.as_uri())
        data["usage"] = (
            "File is on the MCP server's computer. Import it through the dashboard's supported "
            "asset workflow; this is not a hosted URL. Video playback depends on the client."
        )
    return MediaResult(
        response=build_entity_response(
            payload=data, api_version=settings.api_version,
            request_id=getattr(client, "last_request_id", None),
        ),
        image=body if data["inline_image"] else None,
    )


def _video_url(creative: dict[str, Any], *, client: LinkedInClient) -> tuple[Any, Any]:
    # Creative assetURL can be a JPEG even for SPONSORED_VIDEO. Resolve the video itself.
    reference = _extract_content_reference(creative.get("content"))
    if not reference or not reference.startswith(("urn:li:share:", "urn:li:ugcPost:")):
        raise LinkedInValidationError("This creative has no supported video post reference")
    try:
        post, _ = _fetch_share_payload(client=client, share_urn=reference)
        media = post.get("content", {}).get("media", {})
        urn = media.get("id")
        if not isinstance(urn, str) or not re.fullmatch(r"urn:li:video:[A-Za-z0-9_-]+", urn):
            raise LinkedInValidationError("The post does not contain a supported LinkedIn video URN")
        video = client.get_json(f"videos/{quote(urn, safe='')}", params={})
    except LinkedInPermissionError as exc:
        raise LinkedInPermissionError(
            "Video download requires access to this post and the Videos API. "
            "Use kind=preview for the available thumbnail; check the app's API permissions "
            "for the full video.",
            status_code=exc.status_code, request_id=exc.request_id, details=exc.details,
        ) from exc
    if video.get("status") not in (None, "AVAILABLE"):
        raise LinkedInValidationError("The video is not yet available for download")
    return video.get("downloadUrl"), video.get("downloadUrlExpiresAt")


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https" or not host.endswith(".licdn.com")
        or parsed.port not in (None, 443) or parsed.username is not None
        or parsed.password is not None or parsed.fragment
    ):
        raise LinkedInValidationError("Media downloads require an HTTPS LinkedIn CDN URL")


def _download(url: str, *, kind: str, timeout: float) -> tuple[bytes, str]:
    limit = IMAGE_LIMIT if kind == "preview" else VIDEO_LIMIT
    # Separate client: never forward the LinkedIn API bearer token to a media host.
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as http:
            for _ in range(4):
                _validate_url(url)
                with http.stream("GET", url) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise LinkedInAPIError("Media redirect has no destination")
                        url = urljoin(url, location)
                        continue
                    if response.status_code != 200:
                        raise LinkedInAPIError(
                            "Media download failed. Retry the tool to obtain a fresh URL.",
                            status_code=response.status_code,
                        )
                    mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    prefix = "image/" if kind == "preview" else "video/"
                    if mime not in EXTENSIONS or not mime.startswith(prefix):
                        raise LinkedInValidationError(f"Expected a supported {kind} file, got {mime or 'unknown type'}")
                    length = response.headers.get("content-length")
                    if length and int(length) > limit:
                        raise LinkedInValidationError(f"Media exceeds the {limit // 1024 // 1024} MiB limit")
                    body = bytearray()
                    for chunk in response.iter_bytes(64 * 1024):
                        if len(body) + len(chunk) > limit:
                            raise LinkedInValidationError(f"Media exceeds the {limit // 1024 // 1024} MiB limit")
                        body.extend(chunk)
                    if not _matches_type(body, mime):
                        raise LinkedInValidationError("Downloaded file does not match its media type")
                    return bytes(body), mime
            raise LinkedInAPIError("Too many media redirects")
    except httpx.HTTPError as exc:
        # HTTP exceptions can include signed URLs: keep them out of tool output/logs.
        raise LinkedInAPIError("Media download failed due to a network error; retry the tool") from exc


def _matches_type(body: bytes | bytearray, mime: str) -> bool:
    if mime == "image/jpeg":
        return body.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/gif":
        return body[:6] in (b"GIF87a", b"GIF89a")
    if mime == "image/webp":
        return body[:4] == b"RIFF" and body[8:12] == b"WEBP"
    return mime == "video/mp4" and body[4:8] == b"ftyp"


def _save(body: bytes, *, directory: Path, filename: str) -> Path:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / filename
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path
