"""Single-user OAuth for the local stdio server. Never return credentials to MCP."""
from __future__ import annotations

from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
import secrets
import tempfile
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from .config import LinkedInAdsSettings, validate_redirect_uri
from .errors import LinkedInAuthError

TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
SCOPES = "r_ads r_ads_reporting"
LOGIN_TTL = 600


@dataclass(repr=False)
class _PendingLogin:
    state: str
    url: str
    deadline: float
    stop: threading.Event = field(default_factory=threading.Event)


class LinkedInAuth:
    def __init__(self, settings: LinkedInAdsSettings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self._pending: _PendingLogin | None = None
        self._thread: threading.Thread | None = None
        self._tokens: dict[str, Any] = {}
        self._error: str | None = None
        self._rejected = False
        if self.configured:
            self._load()

    @property
    def configured(self) -> bool:
        return bool(self.settings.client_id and self.settings.client_secret)

    def _failure(self, message: str) -> LinkedInAuthError:
        return LinkedInAuthError(message, details={"next_tool": "linkedin_login"})

    def _load(self) -> None:
        try:
            data = json.loads(self.settings.token_file.read_text())
            if not isinstance(data, dict) or data.get("client_id") != self.settings.client_id:
                return
            if not isinstance(data.get("access_token"), str) or not data["access_token"]:
                raise ValueError
            for key in ("expires_at", "refresh_expires_at"):
                if key in data and (
                    not isinstance(data[key], (int, float)) or not math.isfinite(data[key])
                ):
                    raise ValueError
            if "refresh_token" in data and not isinstance(data["refresh_token"], str):
                raise ValueError
            self._tokens = data
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self._error = "Saved login could not be read. Use linkedin_login to reconnect."

    def _save(self, tokens: dict[str, Any]) -> None:
        path = self.settings.token_file
        temporary: str | None = None
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".linkedin-", dir=path.parent)
            with os.fdopen(fd, "w") as output:
                os.fchmod(output.fileno(), 0o600)
                json.dump(tokens, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
        except OSError:
            raise self._failure("Could not save login. Check LINKEDIN_TOKEN_FILE permissions.") from None
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self._tokens = tokens
        self._rejected = False
        self._error = None

    def _exchange(self, fields: dict[str, str], *, refresh: bool = False) -> None:
        try:
            response = httpx.post(
                TOKEN_URL,
                data={
                    **fields,
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                },
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
            )
            if response.status_code != 200:
                raise ValueError
            data = response.json()
            token = data["access_token"]
            lifetime = int(data["expires_in"])
            if not isinstance(token, str) or not token or lifetime <= 0:
                raise ValueError
            tokens = {
                "client_id": self.settings.client_id,
                "access_token": token,
                "expires_at": time.time() + lifetime,
            }
            refresh_token = data.get("refresh_token")
            if refresh_token:
                if not isinstance(refresh_token, str):
                    raise ValueError
                tokens["refresh_token"] = refresh_token
            elif refresh and self._tokens.get("refresh_token"):
                tokens["refresh_token"] = self._tokens["refresh_token"]
            if "refresh_token_expires_in" in data:
                tokens["refresh_expires_at"] = time.time() + int(data["refresh_token_expires_in"])
            elif refresh and "refresh_expires_at" in self._tokens:
                tokens["refresh_expires_at"] = self._tokens["refresh_expires_at"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError, OverflowError):
            # LinkedIn's response body and HTTP exceptions can include credentials.
            raise self._failure(
                "LinkedIn token exchange failed. Use linkedin_login to reconnect; "
                "check the app credentials, redirect URI and Ads permissions if it persists."
            ) from None
        self._save(tokens)

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            token = self._tokens.get("access_token") or self.settings.access_token
            expires_at = self._tokens.get("expires_at")
            expired = expires_at is not None and expires_at <= time.time() + 60
            if force_refresh or expired or self._rejected:
                refresh_token = self._tokens.get("refresh_token")
                refresh_expiry = self._tokens.get("refresh_expires_at")
                if self.configured and refresh_token and (
                    refresh_expiry is None or refresh_expiry > time.time()
                ):
                    try:
                        self._exchange({"grant_type": "refresh_token", "refresh_token": refresh_token},
                                       refresh=True)
                    except LinkedInAuthError as exc:
                        self._error = exc.message
                        raise
                    return str(self._tokens["access_token"])
                raise self._failure("LinkedIn login expired or was rejected. Use linkedin_login.")
            if not token:
                raise self._failure("LinkedIn is not connected. Use linkedin_login.")
            return str(token)

    def mark_rejected(self) -> None:
        with self._lock:
            self._rejected = True

    def status(self) -> dict[str, Any]:
        with self._lock:
            expiry = self._tokens.get("expires_at")
            has_token = bool(self._tokens.get("access_token") or self.settings.access_token)
            pending = self._pending is not None and self._pending.deadline > time.monotonic()
            state = "token_available" if has_token else "not_connected"
            if self._rejected or (expiry is not None and expiry <= time.time()):
                state = "login_required"
            if pending:
                state = "awaiting_login"
            return {
                "status": state,
                "oauth_configured": self.configured,
                "expires_at": expiry,
                "refresh_available": bool(self._tokens.get("refresh_token")) and (
                    self._tokens.get("refresh_expires_at", float("inf")) > time.time()
                ),
                "error": self._error,
                "note": "Local login status only; use list_ad_accounts to verify access with LinkedIn.",
            }

    def login(self) -> dict[str, Any]:
        if not self.configured:
            raise self._failure(
                "Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in the MCP server configuration "
                "and register LINKEDIN_REDIRECT_URI in the LinkedIn app, then restart the server. "
                "Do not send the client secret in chat."
            )
        validate_redirect_uri(self.settings.redirect_uri)
        with self._lock:
            if self._pending and self._pending.deadline > time.monotonic():
                return self._login_result(self._pending)
        self.close()
        with self._lock:
            state = secrets.token_urlsafe(32)
            pending = _PendingLogin(
                state=state,
                url="https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
                    "response_type": "code", "client_id": self.settings.client_id,
                    "redirect_uri": self.settings.redirect_uri, "scope": SCOPES, "state": state,
                }),
                deadline=time.monotonic() + LOGIN_TTL,
            )
            owner = self

            class Callback(BaseHTTPRequestHandler):
                def setup(self) -> None:
                    self.request.settimeout(5)
                    super().setup()

                def log_message(self, format: str, *args: Any) -> None:
                    pass  # Callback URLs contain an authorization code; never log them.

                def do_GET(self) -> None:
                    code, message = owner._callback(self.path, pending)
                    body = message.encode("utf-8")
                    self.send_response(code)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)

            try:
                port = urlsplit(self.settings.redirect_uri).port
                assert port is not None  # Validated before opening the listener.
                listener = HTTPServer(("127.0.0.1", port), Callback)
            except OSError:
                raise self._failure(
                    "Cannot open the local login callback. Close the other login/server using "
                    "this port or configure a different LINKEDIN_REDIRECT_URI."
                ) from None
            listener.timeout = 0.2
            self._pending = pending
            self._error = None
            self._thread = threading.Thread(target=self._serve, args=(listener, pending), daemon=True)
            self._thread.start()
            return self._login_result(pending)

    def _login_result(self, pending: _PendingLogin) -> dict[str, Any]:
        return {
            "status": "awaiting_login",
            "authorization_url": pending.url,
            "expires_in": max(0, int(pending.deadline - time.monotonic())),
            "instructions": "Open authorization_url in a browser on the computer running this "
                            "MCP server. After LinkedIn login, call linkedin_login_status, then retry "
                            "the Ads request. Credentials are saved automatically; no restart needed.",
        }

    def _serve(self, listener: HTTPServer, pending: _PendingLogin) -> None:
        try:
            while not pending.stop.is_set() and time.monotonic() < pending.deadline:
                listener.handle_request()
        finally:
            listener.server_close()
            with self._lock:
                if self._pending is pending:
                    self._pending = None
                    self._error = "Login timed out. Use linkedin_login again."

    def _callback(self, path: str, pending: _PendingLogin) -> tuple[int, str]:
        parsed = urlsplit(path)
        if parsed.path != urlsplit(self.settings.redirect_uri).path:
            return 404, "Not found."
        query = parse_qs(parsed.query)
        with self._lock:
            states = query.get("state", [])
            if (self._pending is not pending or time.monotonic() >= pending.deadline
                    or len(states) != 1
                    or not secrets.compare_digest(states[0].encode(), pending.state.encode())):
                return 400, "Invalid or expired login. Start a new login from your MCP client."
            self._pending = None  # Consume state before exchanging the one-time authorization code.
            pending.stop.set()
            if "error" in query:
                self._error = "LinkedIn login was cancelled or denied. Use linkedin_login again."
                return 400, self._error
            codes = query.get("code", [])
            if len(codes) != 1:
                self._error = "Missing authorization code. Use linkedin_login again."
                return 400, self._error
            try:
                self._exchange({"grant_type": "authorization_code", "code": codes[0],
                                "redirect_uri": self.settings.redirect_uri})
            except LinkedInAuthError as exc:
                self._error = exc.message
                return 400, exc.message
            return 200, "LinkedIn Ads verbunden. Du kannst zum Chat zurueckkehren."

    def close(self) -> None:
        with self._lock:
            if self._pending:
                self._pending.stop.set()
                self._pending = None
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=self.settings.timeout_seconds + 6)
