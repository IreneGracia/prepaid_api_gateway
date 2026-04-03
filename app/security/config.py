import os

from dotenv import load_dotenv

load_dotenv()

'''
Centralised security configuration.

All values are mutable at runtime via the developer dashboard.
Initial values come from environment variables.
Middleware reads from this module on every request, so changes take effect immediately.
'''

# ── Rate limiting ──
RATE_LIMIT_PER_KEY = int(os.getenv("SEC_RATE_LIMIT_PER_KEY", "60"))
RATE_LIMIT_PER_IP = int(os.getenv("SEC_RATE_LIMIT_PER_IP", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("SEC_RATE_LIMIT_WINDOW", "60"))

# ── DDoS protection ──
DDOS_BURST_THRESHOLD = int(os.getenv("SEC_DDOS_BURST_THRESHOLD", "20"))
DDOS_BURST_WINDOW_SECONDS = int(os.getenv("SEC_DDOS_BURST_WINDOW", "5"))
DDOS_COOLDOWN_SECONDS = int(os.getenv("SEC_DDOS_COOLDOWN", "30"))

# ── JWT / Auth ──
SEC_AUTH_ENABLED = os.getenv("SEC_AUTH_ENABLED", "false").lower() == "true"
JWT_SECRET = os.getenv("SEC_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("SEC_JWT_EXPIRE_MINUTES", "60"))
ADMIN_USERNAME = os.getenv("SEC_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("SEC_ADMIN_PASSWORD", "admin")

# ── IP filtering ──
_whitelist_raw = os.getenv("SEC_IP_WHITELIST", "")
_blacklist_raw = os.getenv("SEC_IP_BLACKLIST", "")
IP_WHITELIST = [ip.strip() for ip in _whitelist_raw.split(",") if ip.strip()]
IP_BLACKLIST = [ip.strip() for ip in _blacklist_raw.split(",") if ip.strip()]

# ── Request validation ──
MAX_BODY_SIZE = int(os.getenv("SEC_MAX_BODY_SIZE", str(1 * 1024 * 1024)))  # 1 MB
ALLOWED_CONTENT_TYPES = ["application/json"]

# ── Threat detection ──
BRUTE_FORCE_THRESHOLD = int(os.getenv("SEC_BRUTE_FORCE_THRESHOLD", "10"))
BRUTE_FORCE_WINDOW_SECONDS = int(os.getenv("SEC_BRUTE_FORCE_WINDOW", "300"))
BRUTE_FORCE_BLOCK_SECONDS = int(os.getenv("SEC_BRUTE_FORCE_BLOCK", "600"))
THREAT_LOG_MAX_ENTRIES = 1000

# ── Paths to skip (static assets, health checks) ──
SKIP_PATHS = ("/static/", "/health", "/favicon.ico")


def get_all_settings():
    '''Return all current security settings as a dict.'''
    return {
        "rateLimitPerKey": RATE_LIMIT_PER_KEY,
        "rateLimitPerIp": RATE_LIMIT_PER_IP,
        "rateLimitWindowSeconds": RATE_LIMIT_WINDOW_SECONDS,
        "ddosBurstThreshold": DDOS_BURST_THRESHOLD,
        "ddosBurstWindowSeconds": DDOS_BURST_WINDOW_SECONDS,
        "ddosCooldownSeconds": DDOS_COOLDOWN_SECONDS,
        "ipWhitelist": IP_WHITELIST,
        "ipBlacklist": IP_BLACKLIST,
        "maxBodySize": MAX_BODY_SIZE,
        "bruteForceThreshold": BRUTE_FORCE_THRESHOLD,
        "bruteForceWindowSeconds": BRUTE_FORCE_WINDOW_SECONDS,
        "bruteForceBlockSeconds": BRUTE_FORCE_BLOCK_SECONDS,
    }


def update_settings(settings: dict):
    '''Update security settings at runtime. Only updates keys that are present.'''
    import app.security.config as cfg

    if "rateLimitPerKey" in settings:
        cfg.RATE_LIMIT_PER_KEY = int(settings["rateLimitPerKey"])
    if "rateLimitPerIp" in settings:
        cfg.RATE_LIMIT_PER_IP = int(settings["rateLimitPerIp"])
    if "rateLimitWindowSeconds" in settings:
        cfg.RATE_LIMIT_WINDOW_SECONDS = int(settings["rateLimitWindowSeconds"])
    if "ddosBurstThreshold" in settings:
        cfg.DDOS_BURST_THRESHOLD = int(settings["ddosBurstThreshold"])
    if "ddosBurstWindowSeconds" in settings:
        cfg.DDOS_BURST_WINDOW_SECONDS = int(settings["ddosBurstWindowSeconds"])
    if "ddosCooldownSeconds" in settings:
        cfg.DDOS_COOLDOWN_SECONDS = int(settings["ddosCooldownSeconds"])
    if "ipWhitelist" in settings:
        cfg.IP_WHITELIST = [ip.strip() for ip in settings["ipWhitelist"] if ip.strip()]
        # Re-parse networks for the IP filter middleware
        from app.security.ip_filter import _parse_networks
        import app.security.ip_filter as ipf
        ipf._whitelist_nets = _parse_networks(cfg.IP_WHITELIST)
    if "ipBlacklist" in settings:
        cfg.IP_BLACKLIST = [ip.strip() for ip in settings["ipBlacklist"] if ip.strip()]
        from app.security.ip_filter import _parse_networks
        import app.security.ip_filter as ipf
        ipf._blacklist_nets = _parse_networks(cfg.IP_BLACKLIST)
    if "maxBodySize" in settings:
        cfg.MAX_BODY_SIZE = int(settings["maxBodySize"])
    if "bruteForceThreshold" in settings:
        cfg.BRUTE_FORCE_THRESHOLD = int(settings["bruteForceThreshold"])
    if "bruteForceWindowSeconds" in settings:
        cfg.BRUTE_FORCE_WINDOW_SECONDS = int(settings["bruteForceWindowSeconds"])
    if "bruteForceBlockSeconds" in settings:
        cfg.BRUTE_FORCE_BLOCK_SECONDS = int(settings["bruteForceBlockSeconds"])
