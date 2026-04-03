import logging
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security.config import (
    RATE_LIMIT_PER_IP,
    RATE_LIMIT_PER_KEY,
    RATE_LIMIT_WINDOW_SECONDS,
    SKIP_PATHS,
)

'''
Per-key and per-IP rate limiting middleware.

Uses a sliding window counter stored in-memory.
Each request is tracked by timestamp. Old entries are pruned
on every check to keep memory bounded.
'''

logger = logging.getLogger("security.rate_limiter")

# {identifier: [timestamp, timestamp, ...]}
_requests = defaultdict(list)
_cleanup_counter = 0


def _prune_and_count(key):
    '''Remove timestamps outside the window and return current count.'''
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    _requests[key] = [t for t in _requests[key] if t > cutoff]
    return len(_requests[key])


def _record(key):
    '''Record a new request timestamp.'''
    _requests[key].append(time.time())


def _cleanup():
    '''Periodically remove stale keys to prevent memory growth.'''
    global _cleanup_counter
    _cleanup_counter += 1
    if _cleanup_counter % 500 == 0:
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        stale = [k for k, v in _requests.items() if not v or v[-1] < cutoff]
        for k in stale:
            del _requests[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in SKIP_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("x-api-key")

        _cleanup()

        # Check per-IP limit
        ip_key = f"ip:{client_ip}"
        if _prune_and_count(ip_key) >= RATE_LIMIT_PER_IP:
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "detail": "IP rate limit exceeded"},
                headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
            )
        _record(ip_key)

        # Check per-key limit (if API key provided)
        if api_key:
            key_key = f"key:{api_key}"
            if _prune_and_count(key_key) >= RATE_LIMIT_PER_KEY:
                logger.warning("Rate limit exceeded for key: %s", api_key[:12])
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests", "detail": "API key rate limit exceeded"},
                    headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
                )
            _record(key_key)

        return await call_next(request)
