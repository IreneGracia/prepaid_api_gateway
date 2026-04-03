import ipaddress
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security.config import IP_BLACKLIST, IP_WHITELIST, SKIP_PATHS

'''
IP whitelist / blacklist middleware.

- If a whitelist is configured, only those IPs are allowed.
- If a blacklist is configured, those IPs are blocked.
- Whitelist takes precedence over blacklist.
- Supports CIDR notation (e.g. 192.168.1.0/24).
'''

logger = logging.getLogger("security.ip_filter")


def _parse_networks(ip_list):
    '''Parse a list of IP strings into ipaddress network objects.'''
    networks = []
    for ip in ip_list:
        try:
            networks.append(ipaddress.ip_network(ip, strict=False))
        except ValueError:
            logger.warning("Invalid IP/CIDR in filter config: %s", ip)
    return networks


_whitelist_nets = _parse_networks(IP_WHITELIST) if IP_WHITELIST else []
_blacklist_nets = _parse_networks(IP_BLACKLIST) if IP_BLACKLIST else []


def _ip_matches(client_ip_str, networks):
    '''Check if a client IP matches any network in the list.'''
    try:
        client_ip = ipaddress.ip_address(client_ip_str)
    except ValueError:
        return False
    return any(client_ip in net for net in networks)


class IPFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in SKIP_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Whitelist mode: only allow listed IPs
        if _whitelist_nets:
            if not _ip_matches(client_ip, _whitelist_nets):
                logger.warning("Blocked IP (not in whitelist): %s", client_ip)
                return JSONResponse(
                    status_code=403,
                    content={"error": "Forbidden", "detail": "IP not allowed"},
                )
            return await call_next(request)

        # Blacklist mode: block listed IPs
        if _blacklist_nets:
            if _ip_matches(client_ip, _blacklist_nets):
                logger.warning("Blocked IP (blacklisted): %s", client_ip)
                return JSONResponse(
                    status_code=403,
                    content={"error": "Forbidden", "detail": "IP blocked"},
                )

        return await call_next(request)
