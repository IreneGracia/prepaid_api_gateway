import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security.config import (
    DDOS_BURST_THRESHOLD,
    DDOS_BURST_WINDOW_SECONDS,
    DDOS_COOLDOWN_SECONDS,
    SKIP_PATHS,
)

'''
DDoS protection middleware.

Detects short bursts of requests from a single IP.
If an IP sends too many requests in a short window,
it gets temporarily blocked for a cooldown period.
'''

logger = logging.getLogger("security.ddos")

# {ip: deque of timestamps}
_bursts = defaultdict(lambda: deque(maxlen=DDOS_BURST_THRESHOLD + 10))

# {ip: blocked_until_timestamp}
_blocked_ips = {}


def is_ip_throttled(ip):
    '''Check if an IP is currently in the blocked/cooldown state.'''
    blocked_until = _blocked_ips.get(ip)
    if blocked_until and time.time() < blocked_until:
        return True
    if blocked_until:
        del _blocked_ips[ip]
    return False


class DDoSProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in SKIP_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Check if already blocked
        if is_ip_throttled(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "detail": "Temporarily blocked due to burst activity"},
                headers={"Retry-After": str(DDOS_COOLDOWN_SECONDS)},
            )

        # Record this request
        now = time.time()
        _bursts[client_ip].append(now)

        # Check burst: count requests in the burst window
        cutoff = now - DDOS_BURST_WINDOW_SECONDS
        recent = sum(1 for t in _bursts[client_ip] if t > cutoff)

        if recent > DDOS_BURST_THRESHOLD:
            _blocked_ips[client_ip] = now + DDOS_COOLDOWN_SECONDS
            logger.warning(
                "DDoS burst detected: IP %s sent %d requests in %ds. Blocked for %ds.",
                client_ip, recent, DDOS_BURST_WINDOW_SECONDS, DDOS_COOLDOWN_SECONDS,
            )
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "detail": "Burst detected, temporarily blocked"},
                headers={"Retry-After": str(DDOS_COOLDOWN_SECONDS)},
            )

        return await call_next(request)
