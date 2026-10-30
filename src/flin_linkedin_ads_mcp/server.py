from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any

from .config import LinkedInAdsSettings, load_config
from .auth import LinkedInAuth
from .dispatcher import dispatch_tool
from .errors import AccountSelectionRequired, LinkedInAdsError
from .response import error_response, selection_required_response
from .tool_registry import tool_specs
from .tools.media import MediaResult

logger = logging.getLogger(__name__)

mcp_types: Any = None
Server: Any = None
stdio_server: Any = None

try:  # Optional at import time for local testing without the dependency installed.
    from mcp import types as mcp_types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except Exception:  # pragma: no cover - exercised only when dependency is unavailable.
    pass


def create_server(settings: LinkedInAdsSettings | None = None, client: Any | None = None) -> Any:
    if Server is None or mcp_types is None:
        raise RuntimeError("mcp is required to create the MCP server")

    server = Server("flin-linkedin-ads-mcp")
    resolved_settings = settings or load_config()
    runtime_client = client or _client(resolved_settings)

    @server.list_tools()
    async def list_tools() -> list[Any]:
        return [
            mcp_types.Tool(
                name=spec.name,
                description=spec.description,
                inputSchema=spec.input_schema,
            )
            for spec in tool_specs()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[Any]:
        request_id = getattr(runtime_client, "last_request_id", None)
        media_content: list[Any] = []
        try:
            if name in {"linkedin_login", "linkedin_login_status"}:
                if arguments:
                    raise ValueError(f"{name} does not accept arguments")
                auth = runtime_client.auth
                result = {"ok": True, "data": (
                    auth.login() if name == "linkedin_login" else auth.status()
                )}
            else:
                dispatched = dispatch_tool(
                    name, arguments or {}, settings=resolved_settings, client=runtime_client
                )
                if isinstance(dispatched, MediaResult):
                    result = dispatched.response
                    data = result["data"]
                    if dispatched.image is not None:
                        media_content.append(mcp_types.ImageContent(
                            type="image", data=base64.b64encode(dispatched.image).decode("ascii"),
                            mimeType=data["mime_type"],
                        ))
                    if data.get("file_uri"):
                        media_content.append(mcp_types.ResourceLink(
                            type="resource_link", uri=data["file_uri"],
                            name=data["sha256"] + "." + data["local_path"].rsplit(".", 1)[-1],
                            mimeType=data["mime_type"], size=data["size_bytes"],
                            description="Local media file on the MCP server; import for dashboard use",
                        ))
                else:
                    result = dispatched
        except AccountSelectionRequired as exc:
            result = selection_required_response(
                question=str(exc),
                parameter="ad_account_id",
                choices=exc.choices,
                api_version=resolved_settings.api_version,
                request_id=request_id,
            )
        except LinkedInAdsError as exc:
            result = error_response(
                code=exc.error_code,
                message=exc.message,
                api_version=resolved_settings.api_version,
                request_id=exc.request_id or request_id,
                details=exc.details,
            )
        except PermissionError as exc:
            result = error_response(
                code="permission_error",
                message=str(exc),
                api_version=resolved_settings.api_version,
                request_id=request_id,
            )
        except (ValueError, TypeError, KeyError) as exc:
            result = error_response(
                code="validation_error",
                message=str(exc),
                api_version=resolved_settings.api_version,
                request_id=request_id,
            )
        except Exception:  # pragma: no cover - defensive fallback
            logger.exception("Unexpected server error while handling MCP tool call")
            result = error_response(
                code="linkedin_api_error",
                message="Unexpected server error",
                api_version=resolved_settings.api_version,
                request_id=request_id,
            )

        content = [mcp_types.TextContent(type="text", text=json.dumps(result, separators=(",", ":"), sort_keys=True))]
        return content + media_content if result.get("ok") else content

    return server


def main() -> None:
    if stdio_server is None or Server is None:
        raise RuntimeError("mcp is required to run flin-linkedin-ads-mcp")
    asyncio.run(_main())


async def _main() -> None:
    resolved_settings = load_config()
    with _client(resolved_settings) as runtime_client:
        server = create_server(resolved_settings, client=runtime_client)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def _client(settings: LinkedInAdsSettings):
    from .linkedin_client import LinkedInClient

    return LinkedInClient(
        access_token=settings.access_token,
        api_version=settings.api_version,
        restli_protocol_version=settings.restli_protocol_version,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
        auth=LinkedInAuth(settings),
    )
