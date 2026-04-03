import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

'''
This file is responsible for all local data storage.

We use SQLite because:
- it is very easy to run locally
- it needs no external database server
- it is perfect for a one-week MVP

The database stores:
1. users
2. ledger entries

The ledger is important because instead of storing a single "balance" number,
we store every credit movement as a row:
- +10 credits for a top-up
- -1 credit for an API call

This is better because it gives us an audit trail.
'''

DB_PATH = os.getenv("DB_PATH", "gateway.db")


def get_connection():
    '''
    Create a SQLite connection.

    Why it exists:
    - gives all helpers a consistent way to open the database
    - enables dictionary-like row access via sqlite3.Row
    '''
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    '''
    Create tables if they do not already exist.

    users:
    - one row per developer/user in the MVP
    - each user gets a unique api_key

    ledger_entries:
    - append-only record of all credit changes
    - delta_credits can be positive or negative
    '''
    with get_connection() as connection:
        connection.executescript(
            '''
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              api_key TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS developers (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              email TEXT NOT NULL UNIQUE,
              developer_key TEXT NOT NULL UNIQUE,
              xrpl_address TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS platform_fees (
              id TEXT PRIMARY KEY,
              developer_id TEXT NOT NULL,
              amount_credits INTEGER NOT NULL,
              amount_xrp REAL NOT NULL,
              status TEXT NOT NULL DEFAULT 'unpaid',
              created_at TEXT NOT NULL,
              FOREIGN KEY(developer_id) REFERENCES developers(id)
            );

            CREATE TABLE IF NOT EXISTS api_endpoints (
              id TEXT PRIMARY KEY,
              developer_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT DEFAULT '',
              url TEXT NOT NULL,
              cost_per_call INTEGER NOT NULL DEFAULT 1,
              is_active INTEGER NOT NULL DEFAULT 1,
              auth_header TEXT DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY(developer_id) REFERENCES developers(id)
            );

            CREATE TABLE IF NOT EXISTS api_calls (
              id TEXT PRIMARY KEY,
              endpoint_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              cost INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id),
              FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS ledger_entries (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              delta_credits INTEGER NOT NULL,
              reason TEXT NOT NULL,
              meta TEXT,
              created_at TEXT NOT NULL,
              prev_hash TEXT NOT NULL DEFAULT '',
              hash TEXT NOT NULL DEFAULT '',
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            '''
        )
        connection.commit()


def create_user(name: str, email: str):
    '''
    Create a new user and issue a new API key.

    Input:
    - name
    - email

    Output:
    - a user dictionary including the generated API key

    Why it exists:
    - the app needs a simple onboarding step
    - the API key is what the gateway checks on each request
    '''
    user_id = str(uuid.uuid4())
    api_key = f"pag_{uuid.uuid4().hex}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO users (id, name, email, api_key, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, name, email, api_key, created_at),
        )
        connection.commit()

    return {
        "id": user_id,
        "name": name,
        "email": email,
        "apiKey": api_key,
        "createdAt": created_at,
    }


def find_user_by_email(email: str):
    '''Find a user by their email.'''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def find_user_by_api_key(api_key: str):
    '''
    Find a user by their API key.

    Why it exists:
    - nearly every protected route begins with an API key check
    - the gateway needs to map an incoming key to a user record
    '''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE api_key = ?",
            (api_key,),
        ).fetchone()

    return dict(row) if row else None


def _compute_hash(entry_id, user_id, delta_credits, reason, meta_json, created_at, prev_hash):
    '''
    Compute a SHA-256 hash for a ledger entry.

    The hash covers all entry fields plus the previous entry's hash,
    forming a chain. If any row is modified or deleted, the chain breaks.
    '''
    payload = f"{entry_id}|{user_id}|{delta_credits}|{reason}|{meta_json}|{created_at}|{prev_hash}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_latest_hash(connection, user_id: str) -> str:
    '''Get the hash of the most recent ledger entry for a user.'''
    row = connection.execute(
        '''
        SELECT hash FROM ledger_entries
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (user_id,),
    ).fetchone()
    return row["hash"] if row else ""


def add_credits(user_id: str, delta_credits: int, reason: str, meta=None):
    '''
    Add a ledger entry that changes a user's credit balance.

    Each entry is hashed with SHA-256 and chained to the previous entry's hash,
    creating a tamper-evident audit trail. If any row is modified, the chain breaks.

    Input:
    - user_id: whose balance changes
    - delta_credits: positive for top-ups, negative for usage
    - reason: human-readable reason such as "mock_topup" or "api_call"
    - meta: optional JSON metadata
    '''
    entry_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    meta_json = json.dumps(meta) if meta is not None else None

    with get_connection() as connection:
        prev_hash = _get_latest_hash(connection, user_id)
        entry_hash = _compute_hash(entry_id, user_id, delta_credits, reason, meta_json, created_at, prev_hash)

        connection.execute(
            '''
            INSERT INTO ledger_entries (id, user_id, delta_credits, reason, meta, created_at, prev_hash, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                entry_id,
                user_id,
                delta_credits,
                reason,
                meta_json,
                created_at,
                prev_hash,
                entry_hash,
            ),
        )
        connection.commit()


def get_balance_by_user_id(user_id: str) -> int:
    '''
    Calculate a user's balance by summing all ledger entries.

    Why it exists:
    - we do not store balance directly
    - the ledger is the source of truth
    '''
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT COALESCE(SUM(delta_credits), 0) AS balance
            FROM ledger_entries
            WHERE user_id = ?
            ''',
            (user_id,),
        ).fetchone()

    return int(row["balance"]) if row else 0


def get_balance_by_api_key(api_key: str):
    '''
    Look up a user by API key and return both:
    - the user record
    - the current balance

    Why it exists:
    - this is a common pattern needed by protected routes
    '''
    user = find_user_by_api_key(api_key)
    if not user:
        return None

    return {
        "user": user,
        "balance": get_balance_by_user_id(user["id"]),
    }


def get_ledger_by_user_id(user_id: str):
    '''
    Fetch recent ledger entries for a user.

    Why it exists:
    - the UI needs to show a mini audit trail
    - it helps demonstrate the "prepaid + usage deduction" story
    '''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT id, delta_credits, reason, meta, created_at, prev_hash, hash
            FROM ledger_entries
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 50
            ''',
            (user_id,),
        ).fetchall()

    ledger = []
    for row in rows:
        item = dict(row)
        item["meta"] = json.loads(item["meta"]) if item["meta"] else None
        ledger.append(item)

    return ledger


def record_platform_fee(developer_id: str, amount_credits: int, amount_xrp: float):
    '''Record a platform fee owed by a developer.'''
    fee_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO platform_fees (id, developer_id, amount_credits, amount_xrp, status, created_at)
            VALUES (?, ?, ?, ?, 'unpaid', ?)
            ''',
            (fee_id, developer_id, amount_credits, amount_xrp, created_at),
        )
        connection.commit()

    return fee_id


def get_developer_fees(developer_id: str):
    '''Get total fees owed by a developer.'''
    with get_connection() as connection:
        row = connection.execute(
            '''
            SELECT COALESCE(SUM(amount_credits), 0) AS total_credits,
                   COALESCE(SUM(amount_xrp), 0) AS total_xrp
            FROM platform_fees
            WHERE developer_id = ? AND status = 'unpaid'
            ''',
            (developer_id,),
        ).fetchone()

    return {
        "owedCredits": int(row["total_credits"]),
        "owedXrp": round(float(row["total_xrp"]), 6),
    }


def update_developer_xrpl_address(developer_id: str, xrpl_address: str):
    '''Update a developer's XRPL address.'''
    with get_connection() as connection:
        connection.execute(
            "UPDATE developers SET xrpl_address = ? WHERE id = ?",
            (xrpl_address, developer_id),
        )
        connection.commit()


def verify_ledger(user_id: str) -> dict:
    '''
    Verify the integrity of a user's ledger by recomputing the hash chain.

    Returns:
    - valid: True if every entry's hash matches and the chain is unbroken
    - entries_checked: number of entries verified
    - broken_at: id of the first tampered entry (if any)
    '''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT id, user_id, delta_credits, reason, meta, created_at, prev_hash, hash
            FROM ledger_entries
            WHERE user_id = ?
            ORDER BY created_at ASC
            ''',
            (user_id,),
        ).fetchall()

    prev_hash = ""
    for row in rows:
        row = dict(row)
        expected = _compute_hash(
            row["id"], row["user_id"], row["delta_credits"],
            row["reason"], row["meta"], row["created_at"], prev_hash
        )
        if row["hash"] != expected or row["prev_hash"] != prev_hash:
            return {"valid": False, "entries_checked": 0, "broken_at": row["id"]}
        prev_hash = row["hash"]

    return {"valid": True, "entries_checked": len(rows), "broken_at": None}


# ── Developer functions ──

def create_developer(name: str, email: str, xrpl_address: str = ""):
    '''Create a new developer and issue a developer key.'''
    dev_id = str(uuid.uuid4())
    developer_key = f"dev_{uuid.uuid4().hex}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO developers (id, name, email, developer_key, xrpl_address, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (dev_id, name, email, developer_key, xrpl_address, created_at),
        )
        connection.commit()

    return {
        "id": dev_id,
        "name": name,
        "email": email,
        "developerKey": developer_key,
        "xrplAddress": xrpl_address,
        "createdAt": created_at,
    }


def find_developer_by_key(developer_key: str):
    '''Find a developer by their developer key.'''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM developers WHERE developer_key = ?",
            (developer_key,),
        ).fetchone()
    return dict(row) if row else None


def find_developer_by_id(developer_id: str):
    '''Find a developer by their ID.'''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM developers WHERE id = ?",
            (developer_id,),
        ).fetchone()
    return dict(row) if row else None


def find_developer_by_email(email: str):
    '''Find a developer by their email.'''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM developers WHERE email = ?",
            (email,),
        ).fetchone()
    return dict(row) if row else None


# ── API Endpoint functions ──

def create_api_endpoint(developer_id: str, name: str, description: str,
                        url: str, cost_per_call: int, auth_header: str = ""):
    '''Register a new API endpoint owned by a developer.'''
    endpoint_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO api_endpoints (id, developer_id, name, description, url, cost_per_call, auth_header, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (endpoint_id, developer_id, name, description, url, cost_per_call, auth_header, created_at),
        )
        connection.commit()

    return {
        "id": endpoint_id,
        "name": name,
        "description": description,
        "url": url,
        "costPerCall": cost_per_call,
        "createdAt": created_at,
    }


def get_endpoints_by_developer(developer_id: str):
    '''List all endpoints for a developer.'''
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM api_endpoints WHERE developer_id = ? ORDER BY created_at DESC",
            (developer_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_endpoints():
    '''List all active endpoints with developer names.'''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT e.*, d.name AS developer_name
            FROM api_endpoints e
            JOIN developers d ON e.developer_id = d.id
            WHERE e.is_active = 1
            ORDER BY e.created_at DESC
            '''
        ).fetchall()
    return [dict(row) for row in rows]


def get_endpoint_by_id(endpoint_id: str):
    '''Look up a single endpoint by ID.'''
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM api_endpoints WHERE id = ?",
            (endpoint_id,),
        ).fetchone()
    return dict(row) if row else None


def update_endpoint(endpoint_id: str, name: str, description: str,
                    url: str, cost_per_call: int, is_active: bool,
                    auth_header: str = ""):
    '''Update an endpoint's configuration.'''
    with get_connection() as connection:
        connection.execute(
            '''
            UPDATE api_endpoints
            SET name = ?, description = ?, url = ?, cost_per_call = ?, is_active = ?, auth_header = ?
            WHERE id = ?
            ''',
            (name, description, url, cost_per_call, 1 if is_active else 0, auth_header, endpoint_id),
        )
        connection.commit()


# ── API Call tracking ──

def record_api_call(endpoint_id: str, user_id: str, cost: int):
    '''Record an API call for revenue and usage tracking.'''
    call_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            '''
            INSERT INTO api_calls (id, endpoint_id, user_id, cost, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (call_id, endpoint_id, user_id, cost, created_at),
        )
        connection.commit()

    return call_id


def get_developer_revenue(developer_id: str):
    '''Revenue stats for a developer across all their endpoints.'''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT e.id, e.name, COUNT(c.id) AS call_count, COALESCE(SUM(c.cost), 0) AS total_revenue
            FROM api_endpoints e
            LEFT JOIN api_calls c ON e.id = c.endpoint_id
            WHERE e.developer_id = ?
            GROUP BY e.id
            ORDER BY total_revenue DESC
            ''',
            (developer_id,),
        ).fetchall()

    endpoints = [dict(row) for row in rows]
    total = sum(e["total_revenue"] for e in endpoints)
    return {"totalRevenue": total, "endpoints": endpoints}


def get_developer_usage(developer_id: str):
    '''Recent calls to a developer's endpoints.'''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT c.created_at, e.name AS endpoint_name, u.name AS user_name, c.cost
            FROM api_calls c
            JOIN api_endpoints e ON c.endpoint_id = e.id
            JOIN users u ON c.user_id = u.id
            WHERE e.developer_id = ?
            ORDER BY c.created_at DESC
            LIMIT 50
            ''',
            (developer_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# ── Admin functions ──

def get_all_users():
    '''Get all users with their balances.'''
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()

    users = []
    for row in rows:
        user = dict(row)
        user["balance"] = get_balance_by_user_id(user["id"])
        users.append(user)
    return users


def get_all_developers():
    '''Get all developers.'''
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM developers ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_payments():
    '''Get all XRP payments from the ledger.'''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT l.delta_credits, l.reason, l.meta, l.created_at, u.name AS user_name
            FROM ledger_entries l
            JOIN users u ON l.user_id = u.id
            WHERE l.delta_credits > 0
            ORDER BY l.created_at DESC
            '''
        ).fetchall()

    results = []
    for row in rows:
        item = dict(row)
        if item.get("meta"):
            item["meta"] = json.loads(item["meta"])
        results.append(item)
    return results


def get_all_fees():
    '''Get all platform fees across all developers.'''
    with get_connection() as connection:
        rows = connection.execute(
            '''
            SELECT f.*, d.name AS developer_name
            FROM platform_fees f
            JOIN developers d ON f.developer_id = d.id
            ORDER BY f.created_at DESC
            '''
        ).fetchall()
    return [dict(row) for row in rows]


def get_platform_stats():
    '''Get platform-wide aggregates.'''
    with get_connection() as connection:
        users = connection.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        developers = connection.execute("SELECT COUNT(*) AS c FROM developers").fetchone()["c"]
        endpoints = connection.execute("SELECT COUNT(*) AS c FROM api_endpoints WHERE is_active = 1").fetchone()["c"]
        total_calls = connection.execute("SELECT COUNT(*) AS c FROM api_calls").fetchone()["c"]
        total_revenue = connection.execute("SELECT COALESCE(SUM(cost), 0) AS c FROM api_calls").fetchone()["c"]
        total_credits = connection.execute(
            "SELECT COALESCE(SUM(delta_credits), 0) AS c FROM ledger_entries WHERE delta_credits > 0"
        ).fetchone()["c"]

    return {
        "totalCustomers": users,
        "totalDevelopers": developers,
        "totalEndpoints": endpoints,
        "totalApiCalls": total_calls,
        "totalRevenue": total_revenue,
        "totalCreditsIssued": total_credits,
    }
