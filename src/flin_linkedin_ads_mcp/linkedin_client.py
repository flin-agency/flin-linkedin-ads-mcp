from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit

import httpx

from .auth import LinkedInAuth
from .config import DEFAULT_API_VERSION
from .errors import (
    LinkedInAPIError,
    LinkedInAdsError,
    LinkedInAuthError,
    LinkedInPermissionError,
    LinkedInRateLimitError,
    LinkedInValidationError,
)


@dataclass(slots=True)
class _RequestResult:
    payload: dict[str, Any]
    request_id: str | None


class LinkedInClient:
    def __init__(
        self,
        *,
        access_token: str,
        api_version: str,
        restli_protocol_version: str,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.Client | None = None,
        auth: LinkedInAuth | None = None,
    ) -> None:
        self.auth = auth
        self.access_token = access_token
        self.api_version = api_version
        self.restli_protocol_version = restli_protocol_version
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client or httpx.Client(timeout=self.timeout_seconds)
        self._owns_client = client is None
        self.last_request_id: str | None = None

    def __enter__(self) -> "LinkedInClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self.auth is not None:
            self.auth.close()
        if self._owns_client:
            self._client.close()

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        result = self.request_json("GET", path, params=params)
        self.last_request_id = result.request_id
        return result.payload

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> _RequestResult:
        url = self._build_url(path)
        request_params = dict(params) if params else None
        request_headers = {
            "Authorization": f"Bearer {self.auth.get_access_token() if self.auth else self.access_token}",
            "Linkedin-Version": self.api_version,
            "X-Restli-Protocol-Version": self.restli_protocol_version,
        }
        restli_method_override = self._restli_method_override(method=method, path=path, params=params)
        if restli_method_override is not None:
            request_headers["X-RestLi-Method"] = restli_method_override

        attempts = 0
        refreshed = False
        while True:
            response = self._client.request(
                method,
                url,
                params=request_params,
                headers=request_headers,
                json=dict(json_body or {}) if json_body is not None else None,
            )
            request_id = self._request_id_from_response(response)

            if response.status_code < 400:
                payload = response.json() if response.content else {}
                return _RequestResult(payload=payload if isinstance(payload, dict) else {}, request_id=request_id)

            error = self._error_from_response(response, request_id=request_id)
            if response.status_code == 401 and self.auth is not None:
                self.auth.mark_rejected()
                if not refreshed:
                    request_headers["Authorization"] = (
                        f"Bearer {self.auth.get_access_token(force_refresh=True)}"
                    )
                    refreshed = True
                    continue
            if self._should_retry(response.status_code) and attempts < self.max_retries:
                time.sleep(self._backoff_seconds(attempts))
                attempts += 1
                continue
            raise error

    @staticmethod
    def _build_url(path: str) -> str:
        clean_path = path.lstrip("/")
        return f"https://api.linkedin.com/rest/{clean_path}"

    @staticmethod
    def _request_id_from_response(response: httpx.Response) -> str | None:
        return (
            response.headers.get("x-li-request-id")
            or response.headers.get("x-restli-id")
            or response.headers.get("x-linkedin-id")
        )

    @staticmethod
    def _should_retry(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code < 600

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        return min(2.0**attempt * 0.5, 8.0)

    def _error_from_response(self, response: httpx.Response, *, request_id: str | None) -> LinkedInAdsError:
        payload = _safe_json(response)
        message = (
            str(payload.get("message"))
            if isinstance(payload.get("message"), str)
            else response.text or "LinkedIn API request failed"
        )

        details = {
            "status_code": response.status_code,
            "error": payload,
        }

        if response.status_code == 426:
            details.update(
                requested_api_version=self.api_version,
                suggested_api_version=DEFAULT_API_VERSION,
            )
            return LinkedInValidationError(
                f"LinkedIn no longer serves this endpoint with API version {self.api_version}. "
                f"Set LINKEDIN_API_VERSION={DEFAULT_API_VERSION} and restart the MCP server. "
                "Retired endpoints must also be migrated to their replacement API.",
                status_code=response.status_code, request_id=request_id, details=details,
            )

        if response.status_code == 401:
            details["next_tool"] = "linkedin_login"
            return LinkedInAuthError(
                message + " Use linkedin_login to reconnect.",
                status_code=response.status_code,
                request_id=request_id,
                details=details,
            )

        if response.status_code == 403:
            return LinkedInPermissionError(
                message,
                status_code=response.status_code,
                request_id=request_id,
                details=details,
            )

        if response.status_code == 429:
            return LinkedInRateLimitError(
                message,
                status_code=response.status_code,
                request_id=request_id,
                details=details,
            )

        if response.status_code in {400, 404, 422}:
            return LinkedInValidationError(
                message,
                status_code=response.status_code,
                request_id=request_id,
                details=details,
            )

        return LinkedInAPIError(
            message,
            status_code=response.status_code,
            request_id=request_id,
            details=details,
        )

    @staticmethod
    def _restli_method_override(*, method: str, path: str, params: Mapping[str, Any] | None) -> str | None:
        if method.strip().upper() != "GET":
            return None

        query_keys: set[str] = set()

        split_path = urlsplit(path)
        for key, _ in parse_qsl(split_path.query, keep_blank_values=True):
            query_keys.add(key)

        if params:
            for key, value in params.items():
                if value is None:
                    continue
                query_keys.add(str(key))

        if "q" in query_keys:
            return "FINDER"
        if "ids" in query_keys:
            return "BATCH_GET"
        return None


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
