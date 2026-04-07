import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

import httpx

from app.db import (
    add_credits,
    create_api_endpoint,
    create_developer,
    create_user,
    authenticate_developer,
    authenticate_user,
    find_developer_by_id,
    find_developer_by_key,
    find_user_by_api_key,
    get_all_developers,
    get_all_endpoints,
    get_all_payments,
    get_all_users,
    get_balance_by_api_key,
    get_balance_by_user_id,
    get_developer_revenue,
    get_developer_usage,
    get_endpoint_by_id,
    get_endpoints_by_developer,
    get_ledger_by_user_id,
    get_platform_stats,
    init_db,
    record_api_call,
    update_developer_xrpl_address,
    update_endpoint,
    verify_ledger,
)
from app.models import (
    CreateEndpointRequest,
    DeveloperRegisterRequest,
    LoginRequest,
    ProxyCallRequest,
    RegisterRequest,
    SummariseRequest,
    UpdateEndpointRequest,
    XamanTopupRequest,
)
from app.xaman import create_payment_request, get_payload_status

load_dotenv()

'''
Main FastAPI application.

Responsibilities:
- load environment variables
- serve the browser UI
- expose API routes
- enforce prepaid access before protected endpoints run
'''

app = FastAPI(title="Prepaid API Gateway")

# Register security middleware and routes.
from app.security import register_security
from app.security.auth import require_admin_auth

register_security(app)

# Read configuration from the environment with sensible defaults.
APP_NAME = os.getenv("APP_NAME", "Prepaid API Gateway")
CREDIT_COST = int(os.getenv("API_CREDIT_COST", "1"))
CREDITS_PER_XRP = int(os.getenv("CREDITS_PER_XRP", "100"))
GATEWAY_SECRET = os.getenv("GATEWAY_SECRET", "")

# Initialise the local SQLite database.
init_db()


# Mount static files so the CSS and JavaScript are served to the browser.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configure Jinja templates for the main HTML page.
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    '''
    Render the main dashboard page.

    Why it exists:
    - gives the project a simple user-friendly interface
    - keeps the MVP easy to demo without Postman or curl
    '''
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": APP_NAME},
    )


@app.get("/portal/customer", response_class=HTMLResponse)
async def customer_portal(request: Request):
    '''Customer portal: register, top up credits, check balance, call endpoints.'''
    return templates.TemplateResponse(
        request=request,
        name="customer_portal.html",
        context={"app_name": APP_NAME},
    )


@app.get("/portal/developer", response_class=HTMLResponse)
async def developer_dashboard(request: Request):
    '''Developer dashboard: register, add endpoints, set pricing, track revenue.'''
    return templates.TemplateResponse(
        request=request,
        name="developer_dashboard.html",
        context={"app_name": APP_NAME},
    )


@app.get("/portal/admin", response_class=HTMLResponse)
async def admin_portal(request: Request, _=Depends(require_admin_auth)):
    '''Admin portal: platform stats, all users, all developers, all escrows.'''
    return templates.TemplateResponse(
        request=request,
        name="admin_portal.html",
        context={"app_name": APP_NAME},
    )


@app.get("/health")
async def health():
    '''
    Simple health check route.

    Why it exists:
    - helpful when verifying the server is up
    - useful for quick deployment smoke checks
    '''
    return {
        "ok": True,
        "app": APP_NAME,
        "xrplEnabled": os.getenv("XRPL_ENABLED", "false").lower() == "true",
    }


@app.get("/api/config")
async def get_config():
    '''Public config — exposes the exchange rate so the UI can display XRP costs.'''
    return {
        "creditsPerXrp": CREDITS_PER_XRP,
        "xrpPerCredit": round(1 / CREDITS_PER_XRP, 8),
    }


@app.post("/api/login")
async def login_user(payload: LoginRequest):
    '''Authenticate a customer by email and password.'''
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail={"error": "Invalid email or password"})
    return {"message": "Signed in", "user": {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "apiKey": user["api_key"],
        "createdAt": user["created_at"],
    }}


@app.post("/api/register")
async def register_user(payload: RegisterRequest):
    '''Register a new customer with username, email, and password.'''
    try:
        user = create_user(payload.name, payload.email, payload.password)
        return {
            "message": "User created",
            "user": user,
        }
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Could not create user",
                "details": str(error),
            },
        ) from error


# Track which Xaman payloads have already been credited (prevent double-credit)
_credited_payloads = set()

# Track payload → api_key/credits/endpoint mapping
_payload_to_apikey = {}
_payload_to_credits = {}
_payload_to_endpoint = {}


@app.post("/api/topup/xrp")
async def topup_xrp(payload: XamanTopupRequest):
    '''
    POST /api/topup/xrp

    Creates a Xaman Payment request. XRP goes directly to the
    developer's XRPL address — the platform never touches the funds.
    '''
    user = find_user_by_api_key(payload.apiKey)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "API key not found"})

    # Look up which endpoint this customer is registered for
    endpoint_id = payload.endpointId if hasattr(payload, 'endpointId') and payload.endpointId else None

    if not endpoint_id:
        raise HTTPException(status_code=400, detail={"error": "Endpoint ID required to determine payment destination"})

    endpoint = get_endpoint_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail={"error": "Endpoint not found"})

    dev = find_developer_by_id(endpoint["developer_id"])
    if not dev or not dev.get("xrpl_address"):
        raise HTTPException(status_code=400, detail={"error": "Developer has no XRPL address configured"})

    result = await create_payment_request(
        destination=dev["xrpl_address"],
        credits=payload.credits,
        api_key=payload.apiKey,
    )

    if result.get("payloadId"):
        _payload_to_apikey[result["payloadId"]] = payload.apiKey
        _payload_to_credits[result["payloadId"]] = payload.credits
        _payload_to_endpoint[result["payloadId"]] = endpoint_id

    return {
        "message": "Scan QR to pay — XRP goes directly to the developer",
        "developerAddress": dev["xrpl_address"],
        **result,
    }


@app.get("/api/topup/xaman/{payload_id}")
async def topup_xaman_status(payload_id: str):
    '''
    GET /api/topup/xaman/{payload_id}

    Check the status of a Xaman payment request.
    If signed, credits the user's account and records the platform fee.
    '''
    result = await get_payload_status(payload_id)

    if result.get("signed") and payload_id not in _credited_payloads:
        api_key = _payload_to_apikey.get(payload_id)
        credits = _payload_to_credits.get(payload_id, 0)
        if api_key and credits > 0:
            user = find_user_by_api_key(api_key)
            if user:
                tx_hash = result.get("txHash")

                # Credit the account
                add_credits(
                    user_id=user["id"],
                    delta_credits=credits,
                    reason="xrpl_topup",
                    meta={
                        "payloadId": payload_id,
                        "txHash": tx_hash,
                        "credits": credits,
                        "senderAddress": result.get("account"),
                    },
                )

                _credited_payloads.add(payload_id)
                result["creditsAdded"] = credits
                result["newBalance"] = get_balance_by_user_id(user["id"])
                print(f"Credited {credits} credits to {api_key} via Xaman payload {payload_id}")

    return result


@app.get("/api/balance/{api_key}")
async def get_balance(api_key: str):
    '''
    GET /api/balance/{api_key}

    Returns the current balance for an API key.

    Why it exists:
    - used by the UI
    - useful for quick manual testing
    '''
    result = get_balance_by_api_key(api_key)
    if not result:
        raise HTTPException(status_code=404, detail={"error": "API key not found"})

    return {
        "name": result["user"]["name"],
        "email": result["user"]["email"],
        "apiKey": result["user"]["api_key"],
        "balance": result["balance"],
    }


@app.get("/api/ledger/{api_key}")
async def get_ledger(api_key: str):
    '''
    GET /api/ledger/{api_key}

    Returns recent balance changes for a key.

    Why it exists:
    - demonstrates the audit trail
    - helps explain why ledger-based accounting is useful
    '''
    user = find_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "API key not found"})

    return {
        "apiKey": user["api_key"],
        "ledger": get_ledger_by_user_id(user["id"]),
        "balance": get_balance_by_user_id(user["id"]),
    }


@app.get("/api/ledger/{api_key}/verify")
async def verify_ledger_integrity(api_key: str):
    '''
    GET /api/ledger/{api_key}/verify

    Verifies the hash chain integrity of a user's ledger.
    Returns whether all entries are untampered.
    '''
    user = find_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "API key not found"})

    result = verify_ledger(user["id"])
    return {
        "apiKey": api_key,
        **result,
    }


def require_credits(x_api_key: str | None):
    '''
    Core prepaid access check.

    It verifies:
    1. was an API key provided?
    2. does that key exist?
    3. does it have enough balance?

    If all checks pass:
    - it returns the matched user

    If any check fails:
    - it raises an HTTP error immediately
    '''
    if not x_api_key:
        raise HTTPException(status_code=401, detail={"error": "Missing x-api-key header"})

    result = get_balance_by_api_key(x_api_key)
    if not result:
        raise HTTPException(status_code=401, detail={"error": "Invalid API key"})

    if result["balance"] < CREDIT_COST:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Insufficient credits",
                "balance": result["balance"],
                "required": CREDIT_COST,
            },
        )

    return result["user"]


@app.post("/api/proxy/summarise")
async def proxy_summarise(payload: SummariseRequest,
                          x_api_key: str | None = Header(default=None),
                          x_gateway_secret: str | None = Header(default=None)):
    '''
    POST /api/proxy/summarise

    Demo upstream API. Summarises text to the first 20 words.

    Accepts either:
    - x-api-key header (direct call with credits)
    - x-gateway-secret header (called by the gateway proxy)
    '''
    # If called via gateway proxy (has gateway secret), skip credit check
    if x_gateway_secret and x_gateway_secret == GATEWAY_SECRET:
        words = payload.text.strip().split()
        summary = " ".join(words[:20])
        return {
            "originalLength": len(payload.text),
            "summary": summary + ("..." if len(words) > 20 else ""),
        }

    # Direct call — require credits
    user = require_credits(x_api_key)

    words = payload.text.strip().split()
    summary = " ".join(words[:20])

    add_credits(
        user_id=user["id"],
        delta_credits=-CREDIT_COST,
        reason="api_call",
        meta={"endpoint": "summarise"},
    )

    return {
        "ok": True,
        "endpoint": "summarise",
        "chargedCredits": CREDIT_COST,
        "remainingBalance": get_balance_by_user_id(user["id"]),
        "data": {
            "originalLength": len(payload.text),
            "summary": summary + ("..." if len(words) > 20 else ""),
        },
    }


# ═══════════════════════════════════════════
# Developer API routes
# ═══════════════════════════════════════════

@app.post("/api/developer/login")
async def login_developer(payload: LoginRequest):
    '''Authenticate a developer by email and password.'''
    dev = authenticate_developer(payload.email, payload.password)
    if not dev:
        raise HTTPException(status_code=401, detail={"error": "Invalid email or password"})
    return {"message": "Signed in", "developer": {
        "id": dev["id"],
        "name": dev["name"],
        "email": dev["email"],
        "developerKey": dev["developer_key"],
        "xrplAddress": dev.get("xrpl_address", ""),
        "createdAt": dev["created_at"],
    }}


@app.post("/api/developer/register")
async def register_developer(payload: DeveloperRegisterRequest):
    '''Register a new developer with username, email, password, and XRPL address.'''
    try:
        dev = create_developer(payload.name, payload.email, payload.password, payload.xrplAddress)
        return {"message": "Developer registered", "developer": dev}
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail={"error": "Could not register developer", "details": str(error)},
        ) from error


@app.post("/api/developer/endpoint")
async def dev_create_endpoint(payload: CreateEndpointRequest):
    '''Add a new API endpoint.'''
    dev = find_developer_by_key(payload.developerKey)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})

    endpoint = create_api_endpoint(
        developer_id=dev["id"],
        name=payload.name,
        description=payload.description,
        url=payload.url,
        cost_per_call=payload.costPerCall,
        auth_header=payload.authHeader,
    )
    return {"message": "Endpoint created", "endpoint": endpoint}


@app.put("/api/developer/endpoint/{endpoint_id}")
async def dev_update_endpoint(endpoint_id: str, payload: UpdateEndpointRequest):
    '''Update an endpoint's configuration.'''
    dev = find_developer_by_key(payload.developerKey)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})

    endpoint = get_endpoint_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail={"error": "Endpoint not found"})

    if endpoint["developer_id"] != dev["id"]:
        raise HTTPException(status_code=403, detail={"error": "Not your endpoint"})

    update_endpoint(endpoint_id, payload.name, payload.description,
                    payload.url, payload.costPerCall, payload.isActive,
                    payload.authHeader)
    return {"message": "Endpoint updated", "endpointId": endpoint_id}


@app.get("/api/developer/{developer_key}/endpoints")
async def dev_list_endpoints(developer_key: str):
    '''List all endpoints for a developer.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})
    return {"endpoints": get_endpoints_by_developer(dev["id"])}


@app.get("/api/developer/{developer_key}/revenue")
async def dev_revenue(developer_key: str):
    '''Revenue stats for a developer.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})
    return get_developer_revenue(dev["id"])


@app.get("/api/developer/{developer_key}/usage")
async def dev_usage(developer_key: str):
    '''Recent usage stats for a developer's endpoints.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})
    return {"calls": get_developer_usage(dev["id"])}


@app.get("/api/developer/{developer_key}/security")
async def dev_get_security(developer_key: str):
    '''Get current security settings.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})

    from app.security.config import get_all_settings
    return get_all_settings()


@app.put("/api/developer/{developer_key}/security")
async def dev_update_security(developer_key: str, request: Request):
    '''Update security settings at runtime.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})

    settings = await request.json()
    from app.security.config import update_settings, get_all_settings
    update_settings(settings)
    return {"message": "Security settings updated", "settings": get_all_settings()}


@app.put("/api/developer/{developer_key}/xrpl-address")
async def dev_update_xrpl(developer_key: str, request: Request):
    '''Update the developer's XRPL address for receiving payments.'''
    dev = find_developer_by_key(developer_key)
    if not dev:
        raise HTTPException(status_code=404, detail={"error": "Developer key not found"})

    body = await request.json()
    xrpl_address = body.get("xrplAddress", "")
    if not xrpl_address or not xrpl_address.startswith("r"):
        raise HTTPException(status_code=400, detail={"error": "Invalid XRPL address"})

    # Verify the address exists on the XRPL testnet
    try:
        from xrpl.clients import JsonRpcClient
        from xrpl.models.requests import AccountInfo
        xrpl_client = JsonRpcClient(os.getenv("XRPL_RPC", "https://s.altnet.rippletest.net:51234"))
        resp = xrpl_client.request(AccountInfo(account=xrpl_address))
        if not resp.is_successful():
            raise HTTPException(status_code=400, detail={"error": "XRPL address not found on testnet"})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "Could not verify XRPL address — check the address and try again"})

    update_developer_xrpl_address(dev["id"], xrpl_address)
    return {"message": "XRPL address updated", "xrplAddress": xrpl_address}


# ═══════════════════════════════════════════
# Gateway proxy routes
# ═══════════════════════════════════════════

@app.get("/api/endpoints")
async def list_endpoints():
    '''List all active API endpoints.'''
    return {"endpoints": get_all_endpoints()}


@app.post("/api/proxy/call")
async def proxy_call(payload: ProxyCallRequest, x_api_key: str | None = Header(default=None)):
    '''
    POST /api/proxy/call

    The core gateway operation. Checks credits, deducts the cost,
    forwards the request to the upstream API, and returns the response.
    '''
    if not x_api_key:
        raise HTTPException(status_code=401, detail={"error": "Missing x-api-key header"})

    result = get_balance_by_api_key(x_api_key)
    if not result:
        raise HTTPException(status_code=401, detail={"error": "Invalid API key"})

    endpoint = get_endpoint_by_id(payload.endpointId)
    if not endpoint:
        raise HTTPException(status_code=404, detail={"error": "Endpoint not found"})

    if not endpoint["is_active"]:
        raise HTTPException(status_code=410, detail={"error": "Endpoint is no longer active"})

    cost = endpoint["cost_per_call"]
    if result["balance"] < cost:
        raise HTTPException(
            status_code=402,
            detail={"error": "Insufficient credits", "balance": result["balance"], "required": cost},
        )

    user = result["user"]

    add_credits(
        user_id=user["id"],
        delta_credits=-cost,
        reason="api_call",
        meta={"endpoint_id": endpoint["id"], "endpoint_name": endpoint["name"]},
    )

    record_api_call(endpoint["id"], user["id"], cost)

    # Forward to upstream with auth headers
    headers = {}
    if GATEWAY_SECRET:
        headers["X-Gateway-Secret"] = GATEWAY_SECRET
    if endpoint.get("auth_header"):
        headers["Authorization"] = endpoint["auth_header"]

    try:
        async with httpx.AsyncClient() as client:
            upstream = await client.post(
                endpoint["url"],
                json=payload.payload,
                headers=headers,
                timeout=30.0,
            )
            upstream_data = upstream.json()
    except Exception as e:
        upstream_data = {"error": "Upstream request failed", "detail": str(e)}

    return {
        "ok": True,
        "endpoint": endpoint["name"],
        "chargedCredits": cost,
        "remainingBalance": get_balance_by_user_id(user["id"]),
        "data": upstream_data,
    }


@app.api_route("/api/proxy/{endpoint_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_passthrough(endpoint_id: str, path: str, request: Request,
                            x_api_key: str | None = Header(default=None)):
    '''
    Catch-all proxy route.

    Forwards any request to the upstream base URL + path.
    The developer registers their base URL once (e.g. https://my-api.com),
    and every path under it is automatically proxied and billed.

    Customer usage:
        GET  /api/proxy/{endpoint_id}/analyse
        POST /api/proxy/{endpoint_id}/translate
        →  forwards to https://my-api.com/analyse, https://my-api.com/translate
    '''
    if not x_api_key:
        raise HTTPException(status_code=401, detail={"error": "Missing x-api-key header"})

    result = get_balance_by_api_key(x_api_key)
    if not result:
        raise HTTPException(status_code=401, detail={"error": "Invalid API key"})

    endpoint = get_endpoint_by_id(endpoint_id)
    if not endpoint:
        raise HTTPException(status_code=404, detail={"error": "Endpoint not found"})

    if not endpoint["is_active"]:
        raise HTTPException(status_code=410, detail={"error": "Endpoint is no longer active"})

    cost = endpoint["cost_per_call"]
    if result["balance"] < cost:
        raise HTTPException(
            status_code=402,
            detail={"error": "Insufficient credits", "balance": result["balance"], "required": cost},
        )

    user = result["user"]

    add_credits(
        user_id=user["id"],
        delta_credits=-cost,
        reason="api_call",
        meta={"endpoint_id": endpoint["id"], "endpoint_name": endpoint["name"], "path": path},
    )

    record_api_call(endpoint["id"], user["id"], cost)

    # Build upstream URL: base URL + path
    base_url = endpoint["url"].rstrip("/")
    upstream_url = f"{base_url}/{path}"

    # Forward headers (exclude host and gateway-specific headers)
    forward_headers = {}
    if GATEWAY_SECRET:
        forward_headers["X-Gateway-Secret"] = GATEWAY_SECRET
    if endpoint.get("auth_header"):
        forward_headers["Authorization"] = endpoint["auth_header"]
    content_type = request.headers.get("content-type")
    if content_type:
        forward_headers["Content-Type"] = content_type

    # Read request body
    body = await request.body()

    try:
        async with httpx.AsyncClient() as client:
            upstream = await client.request(
                method=request.method,
                url=upstream_url,
                content=body if body else None,
                headers=forward_headers,
                params=dict(request.query_params),
                timeout=30.0,
            )

            # Try to return JSON, fall back to text
            try:
                upstream_data = upstream.json()
            except Exception:
                upstream_data = {"raw": upstream.text}

    except Exception as e:
        upstream_data = {"error": "Upstream request failed", "detail": str(e)}

    return {
        "ok": True,
        "endpoint": endpoint["name"],
        "path": path,
        "chargedCredits": cost,
        "remainingBalance": get_balance_by_user_id(user["id"]),
        "data": upstream_data,
    }


# ═══════════════════════════════════════════
# Admin API routes
# ═══════════════════════════════════════════

@app.get("/api/admin/stats")
async def admin_stats(_=Depends(require_admin_auth)):
    '''Platform-wide statistics.'''
    return get_platform_stats()


@app.get("/api/admin/customers")
async def admin_customers(_=Depends(require_admin_auth)):
    '''All customers with balances.'''
    return {"customers": get_all_users()}


@app.get("/api/admin/developers")
async def admin_developers(_=Depends(require_admin_auth)):
    '''All registered developers.'''
    return {"developers": get_all_developers()}


@app.get("/api/admin/endpoints")
async def admin_endpoints(_=Depends(require_admin_auth)):
    '''All endpoints across all developers.'''
    return {"endpoints": get_all_endpoints()}


@app.get("/api/admin/payments")
async def admin_payments(_=Depends(require_admin_auth)):
    '''All XRP payments received.'''
    return {"payments": get_all_payments()}


@app.get("/api/admin/security-log")
async def admin_security_log(_=Depends(require_admin_auth)):
    '''Recent security events.'''
    from app.security.threat_detector import get_threat_log
    return {"events": get_threat_log()}
