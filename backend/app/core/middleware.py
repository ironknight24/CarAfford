import time
import uuid
from typing import Dict, Tuple
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.redis import get_redis_client


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generates or propagates a unique Request ID for request correlation and distributed tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforces hardened HTTP security headers to protect against clickjacking, MIME sniffing, and XSS."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.ENVIRONMENT.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


# In-memory sliding window cache for rate limiting fallback
_in_memory_rate_limits: Dict[str, Tuple[int, float]] = {}


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiting middleware using Redis with in-memory fallback."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.RATE_LIMIT_ENABLED or settings.ENVIRONMENT.lower() == "test":
            return await call_next(request)

        # Skip health probes from rate limiting
        if request.url.path.startswith("/health") or request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        # Identify client by IP (with X-Forwarded-For reverse-proxy support) or auth header
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        auth_header = request.headers.get("Authorization", "")
        client_key = f"rl:{client_ip}:{auth_header[:20]}"

        # Rate limit thresholds
        is_auth_route = "/auth/" in request.url.path
        limit = (
            settings.RATE_LIMIT_AUTH_PER_MIN
            if is_auth_route
            else settings.RATE_LIMIT_DEFAULT_PER_MIN
        )
        window_seconds = 60

        # Try Redis rate limit first
        rate_limited = False
        current_count = 1

        if settings.REDIS_ENABLED:
            try:
                redis_client = await get_redis_client()
                if redis_client:
                    current_count = await redis_client.incr(client_key)
                    if current_count == 1:
                        await redis_client.expire(client_key, window_seconds)
                    if current_count > limit:
                        rate_limited = True
            except Exception:
                # Fallback to in-memory rate limiting on redis connection failure
                rate_limited = self._check_in_memory_limit(client_key, limit, window_seconds)
        else:
            rate_limited = self._check_in_memory_limit(client_key, limit, window_seconds)

        if rate_limited:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Maximum {limit} requests per minute allowed.",
                        "request_id": request_id,
                    }
                },
                headers={
                    "Retry-After": str(window_seconds),
                    "X-Request-ID": request_id,
                },
            )

        return await call_next(request)

    def _check_in_memory_limit(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        count, reset_at = _in_memory_rate_limits.get(key, (0, now + window))
        if now > reset_at:
            _in_memory_rate_limits[key] = (1, now + window)
            return False
        else:
            count += 1
            _in_memory_rate_limits[key] = (count, reset_at)
            return count > limit
