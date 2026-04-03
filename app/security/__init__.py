from fastapi import FastAPI

from app.security.auth import auth_router
from app.security.ddos_protection import DDoSProtectionMiddleware
from app.security.ip_filter import IPFilterMiddleware
from app.security.rate_limiter import RateLimitMiddleware
from app.security.request_validator import RequestValidationMiddleware
from app.security.threat_detector import ThreatDetectionMiddleware

'''
Security module entry point.

Call register_security(app) once from main.py to add all
security middleware and routes in the correct order.

Middleware execution order (outermost to innermost):
  ThreatDetection → IPFilter → DDoS → RateLimit → RequestValidation → App
'''


def register_security(app: FastAPI):
    '''Register all security middleware and routes on the app.'''

    # Middleware is added in reverse order (last added = outermost).
    # We want: Threat → IP → DDoS → Rate → Validation → App
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(DDoSProtectionMiddleware)
    app.add_middleware(IPFilterMiddleware)
    app.add_middleware(ThreatDetectionMiddleware)

    # Auth routes
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
