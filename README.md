# Prepaid API Gateway

A platform that lets developers monetise their APIs using prepaid credits settled on the XRP Ledger. Developers register their API endpoints, set pricing in XRP, and share a registration link with customers. Customers pay with XRP via Xaman wallet — XRP goes directly to the developer's XRPL address. Credits are checked and deducted in real time on every request. The platform never holds funds.

## How it works

```
Developer registers with XRPL address → adds API endpoint → sets price in XRP → gets a shareable link
Customer clicks link → registers → pays XRP (goes directly to developer) → gets credits
Customer calls API → gateway checks balance → deducts credits → forwards request → returns response
```

## Key features

- **Prepaid credit system** — no credits = no access. Zero credit risk
- **Direct XRPL payments** — XRP goes from customer straight to developer's wallet. Platform never touches the funds
- **Non-custodial** — the platform is not a custodian. It orchestrates payments, not holds them
- **Tamper-proof ledger** — every credit movement is SHA-256 hash-chained. Customers can verify integrity
- **Configurable exchange rate** — developer sets `CREDITS_PER_XRP` (e.g. 100 credits per XRP)
- **Security middleware** — rate limiting, DDoS protection, IP filtering, request validation, brute force detection — all configurable from the developer dashboard
- **Developer dashboard** — register with XRPL address, add endpoints, set pricing in XRP, track revenue, configure security
- **Customer portal** — endpoint-specific registration pages (via shared link) with XRP payment and API calling

## Quick start

```bash
pip install -r requirements.txt
rm -f gateway.db
uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001

## Running the demo (step by step)

This walkthrough shows the full flow: developer sets up an API, customer registers and calls it.

### Part 1: Developer setup

**Step 1 — Open the developer dashboard**

Go to http://localhost:8001/portal/developer

**Step 2 — Register as a developer**

- Click "Register new account"
- Enter a username, email, and your XRPL address (from your Xaman wallet — starts with `r`)
- Click "Register"
- Sections 2-5 will unlock after successful registration
- If you already registered, click "Sign in" and enter your email

**Step 3 — Add an API endpoint**

- Fill in the endpoint details:
  - Endpoint name: `Text Summariser`
  - Description: `Summarises text to the first 20 words`
  - Upstream URL: `http://localhost:8001/api/proxy/summarise`
  - Cost per call: `0.01` XRP
- Click "Add endpoint"

**Step 4 — Get the customer link**

- Click "Load my endpoints"
- A table appears with your endpoint
- Click "Copy link" next to the endpoint
- This copies a URL like: `http://localhost:8001/portal/customer?endpoint=abc123...`

### Part 2: Customer experience

**Step 5 — Open the customer link**

- Open a new browser tab (or an incognito window to simulate a different person)
- Paste the customer link you copied in Step 4
- The page shows the endpoint name, description, and cost per call
- Note: going to `/portal/customer` without `?endpoint=` will show an error — customers must use a developer's link

**Step 6 — Register as a customer**

- Click "Register new account"
- Enter a username and email (use a different email than the developer)
- Click "Register new account"
- Your API key will be set (shown as dots for security)
- If you already registered, click "Sign in" and enter your email

**Step 7 — Top up credits**

Option A — Mock top-up (for demo, no real payment):
- Enter the number of credits (e.g. `100`)
- Click "Mock top-up (demo)"
- Credits are added instantly

Option B — Pay with XRP via Xaman (real XRPL testnet payment):
- Enter the number of credits (e.g. `100`)
- Click "Pay with XRP"
- A QR code appears
- Open the Xaman app on your phone and scan the QR code
- Approve the transaction — XRP goes directly to the developer's XRPL address
- Wait a few seconds — the portal polls for confirmation
- Once confirmed, credits are added to your account

**Step 8 — Check your balance**

- Click "Refresh balance"
- The response panel shows your current credit balance and its XRP value

**Step 9 — Call the API**

- Enter a request body, e.g.: `{"text": "The quick brown fox jumps over the lazy dog and then runs across the field to find more adventures in the forest"}`
- Click "Call endpoint"
- The response panel shows the summarised text, credits charged, and remaining balance

**Step 10 — Check the ledger**

- Click "Load ledger"
- Shows every credit movement: the top-up (+100) and the API call deduction (-1)
- Each entry is timestamped with metadata

**Step 11 — Verify integrity**

- Click "Verify integrity"
- Shows "VALID" with the number of entries checked if the ledger is untampered
- This proves no records have been altered — the SHA-256 hash chain is intact

### Part 3: Developer checks revenue

**Step 12 — Go back to the developer dashboard**

- Go to http://localhost:8001/portal/developer
- Click "Sign in" and enter your developer email

**Step 13 — Check revenue and usage**

- Click "Load revenue" — shows total credits earned and per-endpoint breakdown
- Click "Recent calls" — shows who called, when, which endpoint, and how much it cost

### Part 4: Admin overview

**Step 14 — Open the admin dashboard**

- Go to http://localhost:8001/portal/admin
- Platform stats load automatically (customers, developers, endpoints, calls, revenue, credits issued)
- Click "Load developers" — see all registered developers
- Click "Load endpoints" — see all API endpoints across all developers
- Click "Load customers" — see all customers with their balances
- Click "Load payments" — see all XRP payments received

## Interfaces

| Interface | URL | Who uses it |
|---|---|---|
| Landing page | `http://localhost:8001` | Links to developer dashboard and admin |
| Developer dashboard | `http://localhost:8001/portal/developer` | Developers: register, add endpoints, track revenue, configure security |
| Customer portal | `http://localhost:8001/portal/customer?endpoint=ID` | Customers: register, top up, call API (requires endpoint link from developer) |
| Admin dashboard | `http://localhost:8001/portal/admin` | Platform operator: overview of all activity |
| API docs (auto-generated) | `http://localhost:8001/docs` | Interactive API documentation (Swagger UI) |

## Project structure

```
app/
  main.py             — FastAPI routes (developer, customer, proxy, admin)
  db.py               — SQLite database (users, developers, endpoints, ledger, calls)
  models.py           — Pydantic request models
  xaman.py            — Xaman wallet integration (payment QR codes)
  security/
    __init__.py        — Registers all middleware on the app
    config.py          — Security settings (runtime-configurable via dashboard)
    rate_limiter.py    — Per-key and per-IP rate limiting
    ddos_protection.py — Burst detection and IP throttling
    ip_filter.py       — IP whitelist/blacklist with CIDR support
    request_validator.py — Payload size, content-type, SQL injection/XSS scanning
    threat_detector.py — Brute force detection, suspicious pattern logging
    auth.py            — JWT authentication for admin portal
templates/
  index.html               — Landing page
  _base.html               — Shared layout with nav
  developer_dashboard.html — Developer UI
  customer_portal.html     — Customer UI (requires ?endpoint= parameter)
  admin_portal.html        — Platform admin UI
static/
  common.js     — Shared utilities (fetch helpers, XRP conversion, polling)
  developer.js  — Developer dashboard logic
  customer.js   — Customer portal logic
  admin.js      — Admin dashboard logic
  styles.css    — Global styles
```

## API routes

### Authentication
- `POST /api/login` — sign in as customer by email, returns API key
- `POST /api/developer/login` — sign in as developer by email, returns developer key

### Customer
- `POST /api/register` — register with username and email, get an API key
- `POST /api/topup/xrp` — create Xaman payment (XRP goes directly to developer)
- `POST /api/topup/mock` — add credits (demo)
- `GET /api/topup/xaman/{payload_id}` — check payment status (also credits account when signed)
- `GET /api/balance/{api_key}` — check credit balance
- `GET /api/ledger/{api_key}` — view transaction history
- `GET /api/ledger/{api_key}/verify` — verify ledger integrity
- `POST /api/proxy/call` — call an endpoint by ID
- `POST /api/proxy/{endpoint_id}/{path}` — call any path on an endpoint

### Developer
- `POST /api/developer/register` — register with username, email, and XRPL address
- `POST /api/developer/endpoint` — add an API endpoint
- `PUT /api/developer/endpoint/{id}` — update an endpoint
- `GET /api/developer/{key}/endpoints` — list your endpoints
- `GET /api/developer/{key}/revenue` — revenue stats
- `GET /api/developer/{key}/usage` — recent call logs
- `GET /api/developer/{key}/security` — view security settings
- `PUT /api/developer/{key}/security` — update security settings
- `PUT /api/developer/{key}/xrpl-address` — update XRPL address (validated against testnet)

### Admin
- `GET /api/admin/stats` — platform-wide metrics
- `GET /api/admin/customers` — all customers
- `GET /api/admin/developers` — all developers
- `GET /api/admin/endpoints` — all endpoints
- `GET /api/admin/payments` — all XRP payments
- `GET /api/admin/security-log` — recent security events

### Public
- `GET /api/endpoints` — list all active endpoints
- `GET /api/config` — exchange rate (credits per XRP)
- `GET /health` — health check

## Payment model

1. Customer pays XRP via Xaman → XRP goes **directly to the developer's XRPL address**
2. Platform never holds customer or developer funds (non-custodial)
3. Gateway provisions credits in the local database
4. Credits are non-refundable (same model as OpenAI, Twilio, AWS)
5. All payments are on the public XRPL — independently verifiable by both sides

## How the credit model works

1. Developer registers with their XRPL address and adds API endpoints with pricing in XRP
2. Developer shares a customer registration link for each endpoint
3. Customer clicks the link, registers with a username and email, and receives an API key
4. Customer tops up credits by paying XRP (directly to developer) or using mock credits for demo
5. Customer calls the API using their API key
6. Gateway checks balance → deducts credits → forwards request to developer's upstream API → returns response
7. If balance is insufficient, the request is blocked with HTTP 402
8. All credit movements are SHA-256 hash-chained — customers can verify nothing has been tampered with
9. All XRP payments are recorded on the public XRPL — independently verifiable by both sides

## Configuration (.env)

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Name shown in UI and responses | Prepaid API Gateway |
| `API_CREDIT_COST` | Default credit cost per call | 1 |
| `CREDITS_PER_XRP` | Exchange rate (e.g. 100 = 1 XRP buys 100 credits) | 100 |
| `DB_PATH` | Path to SQLite database file | ./gateway.db |
| `GATEWAY_SECRET` | Shared secret sent as X-Gateway-Secret header to upstream APIs | |
| `XRPL_RPC` | XRPL testnet RPC URL (for address validation) | https://s.altnet.rippletest.net:51234 |
| `XAMAN_API_KEY` | Xaman API key (from apps.xumm.dev) | |
| `XAMAN_API_SECRET` | Xaman API secret | |
| `SEC_AUTH_ENABLED` | Enable JWT auth for admin portal | false |
| `SEC_ADMIN_USERNAME` | Admin login username | admin |
| `SEC_ADMIN_PASSWORD` | Admin login password | admin |
| `SEC_JWT_SECRET` | Secret for signing JWT tokens | |
