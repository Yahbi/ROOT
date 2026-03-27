"""
Pure ASGI security middleware for ROOT.

CRITICAL: These are pure ASGI middleware — NOT BaseHTTPMiddleware.
BaseHTTPMiddleware causes ~10s blocking per request when stacked.

Middleware stack (outermost first):
    SecurityHeaders -> RateLimiter -> APIKeyAuth -> app
"""

from __future__ import annotations

import hmac
import json
import logging
import time
from typing import Any, Callable, Tuple

from backend.config import API_KEY, RATE_LIMIT_RPM

logger = logging.getLogger("root.security")

# ── Helpers ──────────────────────────────────────────────────────

_JSON_CONTENT_TYPE = b"application/json"


def _get_path(scope: dict) -> str:
    """Extract request path from ASGI scope."""
    return scope.get("path", "")


def _get_header(scope: dict, name: bytes) -> str | None:
    """Extract a header value from ASGI scope (case-insensitive)."""
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("utf-8", errors="replace")
    return None


def _get_query_param(scope: dict, name: str) -> str | None:
    """Extract a query parameter value from ASGI scope."""
    qs = scope.get("query_string", b"").decode("utf-8", errors="replace")
    if not qs:
        return None
    for pair in qs.split("&"):
        if "=" in pair:
            key, _, value = pair.partition("=")
            if key == name:
                return value
    return None


def _get_client_ip(scope: dict) -> str:
    """Extract client IP from ASGI scope."""
    client = scope.get("client")
    if client:
        return client[0]
    # Fall back to X-Forwarded-For if behind a proxy
    forwarded = _get_header(scope, b"x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "unknown"


async def _send_json_response(
    send: Callable,
    status: int,
    body: dict[str, Any],
    extra_headers: list[Tuple[bytes, bytes]] | None = None,
) -> None:
    """Send a complete JSON HTTP response via raw ASGI."""
    payload = json.dumps(body).encode("utf-8")
    headers = [
        (b"content-type", _JSON_CONTENT_TYPE),
        (b"content-length", str(len(payload)).encode()),
    ]
    if extra_headers:
        headers.extend(extra_headers)

    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": payload,
    })


def _is_static_path(path: str) -> bool:
    """Check if a path serves static assets."""
    return path.startswith(("/css/", "/js/", "/favicon", "/assets/"))


# ── APIKeyAuth ───────────────────────────────────────────────────


# Paths that never require authentication
_AUTH_SKIP_PREFIXES = ("/api/health", "/docs", "/openapi.json", "/redoc")
_AUTH_SKIP_EXACT = {"/", ""}


class APIKeyAuth:
    """
    Pure ASGI middleware — validates API key from header or query param.

    If ROOT_API_KEY env var is empty/unset, auth is disabled (dev mode).
    Skips auth for health checks, docs, static files, and root path.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app
        self._enabled = bool(API_KEY)
        if self._enabled:
            logger.info("API key auth: ENABLED")
        else:
            logger.info("API key auth: DISABLED (dev mode — no ROOT_API_KEY set)")

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        # WebSocket connections: validate API key from query param
        if scope["type"] == "websocket":
            if not self._enabled:
                await self.app(scope, receive, send)
                return
            provided_key = _get_query_param(scope, "api_key")
            if not provided_key or not hmac.compare_digest(provided_key, API_KEY):
                # Reject WebSocket upgrade — send close before accept
                await send({"type": "websocket.close", "code": 4401})
                return
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Dev mode — no auth
        if not self._enabled:
            await self.app(scope, receive, send)
            return

        path = _get_path(scope)

        # Skip auth for allowed paths
        if path in _AUTH_SKIP_EXACT or _is_static_path(path):
            await self.app(scope, receive, send)
            return

        for prefix in _AUTH_SKIP_PREFIXES:
            if path.startswith(prefix):
                await self.app(scope, receive, send)
                return

        # Check API key from header or query param
        provided_key = (
            _get_header(scope, b"x-api-key")
            or _get_query_param(scope, "api_key")
        )

        if not provided_key or not hmac.compare_digest(provided_key, API_KEY):
            logger.warning("Auth rejected: ip=%s path=%s", _get_client_ip(scope), path)
            await _send_json_response(send, 401, {
                "error": "Unauthorized",
                "detail": "Invalid or missing API key. "
                          "Provide X-API-Key header or api_key query parameter.",
            })
            return

        await self.app(scope, receive, send)


# ── RateLimiter ──────────────────────────────────────────────────


class RateLimiter:
    """
    Pure ASGI middleware — in-memory per-IP rate limiter.

    Default: 100 requests/minute per IP (configurable via ROOT_RATE_LIMIT).
    Skips rate limiting for static file requests.
    Cleans up stale entries every 1000 requests.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app
        self._rpm = RATE_LIMIT_RPM
        self._window = 60.0  # seconds
        # IP -> (request_count, window_start_time)
        self._clients: dict[str, Tuple[int, float]] = {}
        self._request_count = 0
        self._cleanup_interval = 1000
        logger.info("Rate limiter: %d requests/minute per IP", self._rpm)

    def _cleanup_stale(self, now: float) -> None:
        """Remove entries whose window has expired."""
        stale_keys = [
            ip for ip, (_, window_start) in self._clients.items()
            if now - window_start > self._window
        ]
        for ip in stale_keys:
            del self._clients[ip]
        if stale_keys:
            logger.debug("Rate limiter cleanup: removed %d stale entries", len(stale_keys))

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = _get_path(scope)

        # Skip rate limiting for static assets
        if _is_static_path(path):
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        ip = _get_client_ip(scope)

        # Periodic cleanup
        self._request_count += 1
        if self._request_count % self._cleanup_interval == 0:
            self._cleanup_stale(now)

        # Check / update rate for this IP
        entry = self._clients.get(ip)
        if entry is None or now - entry[1] > self._window:
            # New window
            self._clients[ip] = (1, now)
        else:
            count, window_start = entry
            new_count = count + 1
            if new_count > self._rpm:
                retry_after = int(self._window - (now - window_start)) + 1
                logger.warning(
                    "Rate limit exceeded: ip=%s count=%d path=%s",
                    ip, new_count, path,
                )
                await _send_json_response(
                    send, 429,
                    {
                        "error": "Too Many Requests",
                        "detail": f"Rate limit exceeded. Max {self._rpm} requests per minute.",
                        "retry_after_seconds": retry_after,
                    },
                    extra_headers=[(b"retry-after", str(retry_after).encode())],
                )
                return
            self._clients[ip] = (new_count, window_start)

        await self.app(scope, receive, send)


# ── SecurityHeaders ──────────────────────────────────────────────

# Headers injected into every HTTP response
_SECURITY_HEADERS: list[Tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"x-xss-protection", b"1; mode=block"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (
        b"content-security-policy",
        b"default-src 'self'; "
        b"script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://unpkg.com; "
        b"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        b"font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        b"img-src 'self' data: blob: https:; "
        b"connect-src 'self' https: ws: wss:; "
        b"frame-ancestors 'none'",
    ),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]


class SecurityHeaders:
    """
    Pure ASGI middleware — injects security headers into every response.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy (dashboard-friendly)
    - Permissions-Policy (restrictive)
    """

    def __init__(self, app: Callable) -> None:
        self.app = app
        logger.info("Security headers: ACTIVE (%d headers)", len(_SECURITY_HEADERS))

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                existing_headers = list(message.get("headers", []))
                existing_headers.extend(_SECURITY_HEADERS)
                message = {**message, "headers": existing_headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
