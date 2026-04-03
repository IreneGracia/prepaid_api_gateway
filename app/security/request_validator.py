import logging
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.security.config import ALLOWED_CONTENT_TYPES, MAX_BODY_SIZE, SKIP_PATHS

'''
Request validation middleware.

Checks:
1. Payload size — rejects bodies larger than MAX_BODY_SIZE
2. Content-Type — only allows application/json for POST/PUT/PATCH
3. Injection sanitisation — scans for common SQL injection and XSS patterns
'''

logger = logging.getLogger("security.request_validator")

# Common SQL injection patterns
_SQL_PATTERNS = re.compile(
    r"(union\s+select|or\s+1\s*=\s*1|drop\s+table|;\s*--|insert\s+into|delete\s+from"
    r"|update\s+\w+\s+set|exec\s*\(|execute\s*\()",
    re.IGNORECASE,
)

# Common XSS patterns
_XSS_PATTERNS = re.compile(
    r"(<script|javascript\s*:|onerror\s*=|onload\s*=|onclick\s*="
    r"|<iframe|<embed|<object|eval\s*\(|document\.cookie)",
    re.IGNORECASE,
)

_MUTATING_METHODS = {"POST", "PUT", "PATCH"}


def _scan_for_injection(text):
    '''Check a string for SQL injection or XSS patterns.'''
    if _SQL_PATTERNS.search(text):
        return "SQL injection pattern detected"
    if _XSS_PATTERNS.search(text):
        return "XSS pattern detected"
    return None


class RequestValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in SKIP_PATHS):
            return await call_next(request)

        method = request.method

        if method in _MUTATING_METHODS:
            # Check Content-Type
            content_type = request.headers.get("content-type", "")
            ct_base = content_type.split(";")[0].strip().lower()
            if ct_base and ct_base not in ALLOWED_CONTENT_TYPES:
                logger.warning("Rejected content type: %s from %s", content_type, request.client.host)
                return JSONResponse(
                    status_code=415,
                    content={"error": "Unsupported Media Type", "detail": f"Expected: {ALLOWED_CONTENT_TYPES}"},
                )

            # Check payload size
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_BODY_SIZE:
                logger.warning("Rejected oversized payload: %s bytes from %s", content_length, request.client.host)
                return JSONResponse(
                    status_code=413,
                    content={"error": "Payload Too Large", "detail": f"Max size: {MAX_BODY_SIZE} bytes"},
                )

            # Read body and scan for injection
            body = await request.body()

            if len(body) > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Payload Too Large"},
                )

            if body:
                body_text = body.decode("utf-8", errors="ignore")
                threat = _scan_for_injection(body_text)
                if threat:
                    logger.warning(
                        "Blocked malicious request from %s: %s",
                        request.client.host, threat,
                    )
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Bad Request", "detail": threat},
                    )

        return await call_next(request)
