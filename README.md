# Prepaid API Gateway

A platform that lets developers monetise their APIs using prepaid credits settled on the XRP Ledger. Developers register their API endpoints, set pricing in XRP, and share a registration link with customers. Customers pay with XRP via Xaman wallet, receive credits, and call the API — credits are checked and deducted in real time on every request.

## How it works

```
Developer registers API endpoint → sets price per call in XRP → gets a shareable link
Customer clicks link → registers → tops up credits with XRP → calls the API
Gateway checks balance → deducts credits → forwards request to upstream → returns response
```

## Key features

- **Prepaid credit system** — no credits = no access. Zero credit risk
- **XRPL payments** — customers pay with XRP via Xaman wallet (testnet). Instant, global, near-zero fees
- **Non-custodial escrow** — XRP locked on-chain via XRPL escrow, gateway never holds customer funds
- **Real proxy forwarding** — gateway forwards requests to the developer's upstream API with auth headers
- **Tamper-proof ledger** — every credit movement is SHA-256 hash-chained. Customers can verify integrity
- **Configurable exchange rate** — developer sets `CREDITS_PER_XRP` (e.g. 100 credits per XRP)
- **Security middleware** — rate limiting, DDoS protection, IP filtering, request validation, brute force detection — all configurable from the developer dashboard
- **Developer dashboard** — register endpoints, set pricing, track revenue, configure security
- **Customer portal** — endpoint-specific registration pages with top-up and API calling

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Open http://localhost:8001

## Running the demo (step by step)

This walkthrough shows the full flow: developer sets up an API, customer registers and calls it.

### Part 1: Developer setup

**Step 1 — Open the developer dashboard**

Go to http://localhost:8001/portal/developer

**Step 2 — Register as a developer**

- Enter your name and email
- Click "Register new account"
- Your developer key (`dev_*`) will appear in the "Developer key" field
- If you already registered, just enter your email and click "Sign in"

**Step 3 — Add an API endpoint**

- Your developer key should already be filled in from Step 2
- Fill in the endpoint details:
  - Name: `Text Summariser`
  - Description: `Summarises text to the first 20 words`
  - Upstream URL: `http://localhost:8001/api/proxy/summarise`
  - Cost per call: `0.01` XRP
- Click "Add endpoint"
- The response panel will show the new endpoint with its `id`

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

- Enter a name and email (use a different email than the developer)
- Click "Register new account"
- Your API key (`pag_*`) will appear in the "API key" field
- If you already registered, just enter your email and click "Sign in"

**Step 7 — Top up credits**

Option A — Mock top-up (for demo, no real payment):
- Enter the number of credits (e.g. `100`)
- Click "Mock top-up (demo)"
- Credits are added instantly

Option B — Pay with XRP via Xaman (real XRPL testnet payment):
- Enter the number of credits (e.g. `100`)
- Click "Pay with XRP (non-custodial)"
- A QR code appears
- Open the Xaman app on your phone and scan the QR code
- Approve the transaction in Xaman
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
- Sign in with your developer email

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
- Click "Load escrows" — see all XRPL escrows (if any XRP payments were made)

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
  db.py               — SQLite database (users, developers, endpoints, escrows, ledger, calls)
  models.py           — Pydantic request models
  xaman.py            — Xaman wallet integration (escrow QR codes)
  xrpl_listener.py    — XRPL websocket listener for incoming payments/escrows
  escrow.py           — XRPL escrow operations (finish/cancel)
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
- `POST /api/register` — register and get an API key
- `POST /api/topup/mock` — add credits (demo)
- `POST /api/topup/escrow` — create Xaman escrow request (non-custodial XRP payment)
- `GET /api/topup/xaman/{payload_id}` — check payment status (also credits account when signed)
- `GET /api/balance/{api_key}` — check credit balance
- `GET /api/ledger/{api_key}` — view transaction history
- `GET /api/ledger/{api_key}/verify` — verify ledger integrity
- `POST /api/proxy/call` — call an endpoint by ID
- `POST /api/proxy/{endpoint_id}/{path}` — call any path on an endpoint
- `GET /api/escrow/{api_key}` — view escrow status
- `POST /api/escrow/{api_key}/claim` — claim consumed credits from escrow

### Developer
- `POST /api/developer/register` — register and get a developer key
- `POST /api/developer/endpoint` — add an API endpoint
- `PUT /api/developer/endpoint/{id}` — update an endpoint
- `GET /api/developer/{key}/endpoints` — list your endpoints
- `GET /api/developer/{key}/revenue` — revenue stats
- `GET /api/developer/{key}/usage` — recent call logs
- `GET /api/developer/{key}/security` — view security settings
- `PUT /api/developer/{key}/security` — update security settings

### Admin
- `GET /api/admin/stats` — platform-wide metrics
- `GET /api/admin/customers` — all customers
- `GET /api/admin/developers` — all developers
- `GET /api/admin/endpoints` — all endpoints
- `GET /api/admin/escrows` — all escrows
- `GET /api/admin/security-log` — recent security events

### Public
- `GET /api/endpoints` — list all active endpoints
- `GET /api/config` — exchange rate (credits per XRP)
- `GET /health` — health check

## Configuration (.env)

| Variable | Description | Default |
|---|---|---|
| `APP_NAME` | Name shown in UI and responses | Prepaid API Gateway |
| `API_CREDIT_COST` | Default credit cost per call | 1 |
| `CREDITS_PER_XRP` | Exchange rate (e.g. 100 = 1 XRP buys 100 credits) | 100 |
| `DB_PATH` | Path to SQLite database file | ./gateway.db |
| `GATEWAY_SECRET` | Shared secret sent as X-Gateway-Secret header to upstream APIs | |
| `XRPL_ENABLED` | Enable the XRPL websocket listener | true |
| `XRPL_SERVER` | XRPL testnet websocket URL | wss://s.altnet.rippletest.net:51233 |
| `XRPL_RPC` | XRPL testnet RPC URL | https://s.altnet.rippletest.net:51234 |
| `XRPL_RECEIVER_ADDRESS` | Gateway's XRPL testnet address | |
| `XRPL_RECEIVER_SEED` | Gateway's XRPL testnet wallet seed | |
| `XAMAN_API_KEY` | Xaman API key (from apps.xumm.dev) | |
| `XAMAN_API_SECRET` | Xaman API secret | |
| `SEC_AUTH_ENABLED` | Enable JWT auth for admin portal | false |
| `SEC_ADMIN_USERNAME` | Admin login username | admin |
| `SEC_ADMIN_PASSWORD` | Admin login password | admin |
| `SEC_JWT_SECRET` | Secret for signing JWT tokens | |

## How the credit model works

1. Developer registers an API endpoint and sets a price in XRP per call
2. Developer shares a customer registration link
3. Customer clicks the link, registers, and receives an API key
4. Customer tops up credits by paying XRP (via Xaman escrow or mock for demo)
5. Customer calls the API using their API key
6. Gateway checks balance → deducts credits → forwards request to developer's upstream API → returns response
7. If balance is insufficient, the request is blocked with HTTP 402
8. All credit movements are SHA-256 hash-chained — customers can verify nothing has been tampered with
9. All XRP payments are recorded on the public XRPL — independently verifiable by both sides
