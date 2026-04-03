import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security.config import (
    BRUTE_FORCE_BLOCK_SECONDS,
    BRUTE_FORCE_THRESHOLD,
    BRUTE_FORCE_WINDOW_SECONDS,
    SKIP_PATHS,
    THREAT_LOG_MAX_ENTRIES,
)

'''
Threat detection middleware.

1. Brute force detection — tracks failed auth attempts per IP.
   If threshold exceeded, IP is temporarily blocked.
2. Suspicious pattern logging — records blocked requests,
   repeated 404s, and injection attempts in a ring buffer.
3. Exposes get_threat_log() for the admin security-log endpoint.
'''

logger = logging.getLogger("security.threat_detector")

# Ring buffer of threat events
_threat_log = deque(maxlen=THREAT_LOG_MAX_ENTRIES)

# {ip: [timestamp, ...]} for failed auth tracking
_failed_auths = defaultdict(list)

# {ip: blocked_until_timestamp}
_brute_force_blocked = {}

# {ip: count} for repeated 404 tracking
_repeated_404s = defaultdict(list)


def get_threat_log(limit=100):
    '''Return the most recent threat events.'''
    return list(_threat_log)[-limit:]


def _log_event(event_type, ip, path, detail=""):
    '''Add an event to the threat log.'''
    event = {
        "type": event_type,
        "ip": ip,
        "path": path,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _threat_log.append(event)
    logger.warning("Threat event: %s", event)


def _is_brute_force_blocked(ip):
    '''Check if an IP is blocked for brute force.'''
    blocked_until = _brute_force_blocked.get(ip)
    if blocked_until and time.time() < blocked_until:
        return True
    if blocked_until:
        del _brute_force_blocked[ip]
    return False


def _track_failed_auth(ip, path):
    '''Track a failed auth attempt and block if threshold exceeded.'''
    now = time.time()
    cutoff = now - BRUTE_FORCE_WINDOW_SECONDS
    _failed_auths[ip] = [t for t in _failed_auths[ip] if t > cutoff]
    _failed_auths[ip].append(now)

    if len(_failed_auths[ip]) >= BRUTE_FORCE_THRESHOLD:
        _brute_force_blocked[ip] = now + BRUTE_FORCE_BLOCK_SECONDS
        _log_event("brute_force_blocked", ip, path,
                   f"Blocked for {BRUTE_FORCE_BLOCK_SECONDS}s after {len(_failed_auths[ip])} failed attempts")
        _failed_auths[ip] = []


class ThreatDetectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in SKIP_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Check brute force block
        if _is_brute_force_blocked(client_ip):
            _log_event("brute_force_rejected", client_ip, path, "Request during block period")
            return JSONResponse(
                status_code=403,
                content={"error": "Forbidden", "detail": "Temporarily blocked due to repeated failed attempts"},
            )

        # Process request and observe response
        response = await call_next(request)
        status = response.status_code

        # Track failed auth attempts (401/403)
        if status in (401, 403):
            _track_failed_auth(client_ip, path)
            _log_event("auth_failure", client_ip, path, f"Status {status}")

        # Log rate limit hits
        elif status == 429:
            _log_event("rate_limited", client_ip, path, "Rate limit or DDoS block")

        # Track repeated 404s (potential scanning)
        elif status == 404:
            now = time.time()
            cutoff = now - 60
            _repeated_404s[client_ip] = [t for t in _repeated_404s[client_ip] if t > cutoff]
            _repeated_404s[client_ip].append(now)
            if len(_repeated_404s[client_ip]) > 10:
                _log_event("scan_detected", client_ip, path,
                           f"{len(_repeated_404s[client_ip])} 404s in 60s")

        # Log blocked payloads (injection attempts)
        elif status == 400:
            _log_event("bad_request", client_ip, path, "Possibly malicious payload")

        # Log oversized or wrong content type
        elif status in (413, 415):
            _log_event("validation_blocked", client_ip, path, f"Status {status}")

        return response
