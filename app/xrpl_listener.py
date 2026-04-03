import asyncio
import os

from dotenv import load_dotenv

from app.db import add_credits, find_user_by_api_key, get_balance_by_user_id

load_dotenv()

'''
XRPL top-up listener.

Purpose:
- watch a receiving XRPL address on testnet
- look for incoming payments
- read a memo like: topup:pag_abc123
- convert that payment into credits for the matching API key

This file is optional for the MVP.
The app can be fully demoed with mock top-ups.
'''

XRPL_ENABLED = os.getenv("XRPL_ENABLED", "false").lower()
XRPL_SERVER = os.getenv("XRPL_SERVER")
XRPL_RECEIVER_ADDRESS = os.getenv("XRPL_RECEIVER_ADDRESS")
XRPL_EXPECTED_MEMO_PREFIX = os.getenv("XRPL_EXPECTED_MEMO_PREFIX", "topup:")
CREDITS_PER_XRP = int(os.getenv("CREDITS_PER_XRP", "1"))


def decode_memo(memos):
    '''
    Decode the memo from an XRPL transaction.

    XRPL memos arrive hex-encoded, so we:
    - extract the first memo's MemoData field
    - decode it from hex to UTF-8 text

    Example result:
    "topup:pag_12345"
    '''
    if not isinstance(memos, list) or not memos:
        return None

    first = memos[0] or {}
    memo_hex = ((first.get("Memo") or {}).get("MemoData"))
    if not memo_hex:
        return None

    try:
        return bytes.fromhex(memo_hex).decode("utf-8")
    except Exception:
        return None


async def main():
    '''
    Main XRPL watcher flow.

    It:
    1. connects to XRPL
    2. subscribes to the receiving address
    3. listens for Payment transactions
    4. matches the API key from the memo
    5. converts payment amount into credits
    6. writes a ledger entry

    Note:
    xrpl-py websocket APIs evolve over time. This file is included as a clear,
    commented starting point for the MVP rather than a production-ready listener.
    '''
    if XRPL_ENABLED != "true":
        print("XRPL listener disabled. Set XRPL_ENABLED=true to enable.")
        return

    if not XRPL_SERVER or not XRPL_RECEIVER_ADDRESS:
        print("Missing XRPL_SERVER or XRPL_RECEIVER_ADDRESS in environment.")
        return

    from xrpl.asyncio.clients import AsyncWebsocketClient
    from xrpl.models.requests import Subscribe

    async with AsyncWebsocketClient(XRPL_SERVER) as client:
        print("Connected to XRPL:", XRPL_SERVER)

        await client.request(
            Subscribe(accounts=[XRPL_RECEIVER_ADDRESS])
        )

        print("Watching payments into:", XRPL_RECEIVER_ADDRESS)

        async for event in client:
            try:
                tx = None

                if isinstance(event, dict):
                    tx = event.get("transaction")
                else:
                    candidate = getattr(event, "result", None)
                    if isinstance(candidate, dict):
                        tx = candidate.get("transaction")

                if not tx:
                    continue

                tx_type = tx.get("TransactionType")
                destination = tx.get("Destination")

                print(f"[XRPL] Received tx: type={tx_type}, destination={destination}, account={tx.get('Account')}")

                if destination != XRPL_RECEIVER_ADDRESS:
                    print(f"[XRPL] Skipping — destination {destination} != {XRPL_RECEIVER_ADDRESS}")
                    continue

                memo = decode_memo(tx.get("Memos"))
                if not memo:
                    print("[XRPL] Skipping — no memo found")
                    continue

                print(f"[XRPL] Memo decoded: {memo}")

                amount_raw = tx.get("Amount")
                if not isinstance(amount_raw, str) or not amount_raw.isdigit():
                    print(f"[XRPL] Skipping — invalid amount: {amount_raw}")
                    continue

                amount_drops = int(amount_raw)
                xrp_amount = amount_drops / 1_000_000
                credits = max(1, int(xrp_amount * CREDITS_PER_XRP))

                # ── Handle direct Payment (legacy / mock-compatible) ──
                if tx_type == "Payment" and memo.startswith(XRPL_EXPECTED_MEMO_PREFIX):
                    api_key = memo[len(XRPL_EXPECTED_MEMO_PREFIX):].strip()
                    user = find_user_by_api_key(api_key)

                    if not user:
                        print("No user matched API key in memo:", api_key)
                        continue

                    add_credits(
                        user_id=user["id"],
                        delta_credits=credits,
                        reason="xrpl_topup",
                        meta={
                            "txHash": tx.get("hash"),
                            "amountDrops": amount_drops,
                            "memo": memo,
                        },
                    )

                    print(
                        "Applied XRPL top-up",
                        {
                            "apiKey": api_key,
                            "txHash": tx.get("hash"),
                            "credits": credits,
                            "balance": get_balance_by_user_id(user["id"]),
                        },
                    )

            except Exception as error:
                print("Failed to process XRPL event:", error)


if __name__ == "__main__":
    asyncio.run(main())
