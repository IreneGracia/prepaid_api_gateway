import os

import httpx
from dotenv import load_dotenv

load_dotenv()

'''
Xaman (formerly Xumm) integration.

This module creates payment requests that users can sign with their
Xaman wallet app by scanning a QR code. Once signed, the payment
settles on the XRPL testnet and the listener picks it up.
'''

CREDITS_PER_XRP = int(os.getenv("CREDITS_PER_XRP", "1"))
XAMAN_API_KEY = os.getenv("XAMAN_API_KEY", "")
XAMAN_API_SECRET = os.getenv("XAMAN_API_SECRET", "")
XAMAN_API_URL = "https://xumm.app/api/v1/platform"

HEADERS = {
    "Content-Type": "application/json",
    "X-API-Key": XAMAN_API_KEY,
    "X-API-Secret": XAMAN_API_SECRET,
}


async def create_payment_request(destination: str, credits: int, api_key: str) -> dict:
    '''
    Create a Xaman payment request (payload).

    The user scans the QR code in their Xaman app, which prompts them
    to sign a Payment transaction on the XRPL testnet.

    The memo contains "topup:<api_key>" so the XRPL listener can
    match the payment to the correct user.

    Args:
        destination: XRPL address to receive the payment
        credits: number of credits to buy (converted to XRP using CREDITS_PER_XRP)
        api_key: the user's API key, embedded in the memo
    '''
    # Convert credits to XRP drops
    xrp_amount = credits / CREDITS_PER_XRP
    drops = max(1, int(xrp_amount * 1_000_000))

    memo_text = f"topup:{api_key}"
    memo_hex = memo_text.encode("utf-8").hex().upper()

    payload = {
        "txjson": {
            "TransactionType": "Payment",
            "Destination": destination,
            "Amount": str(drops),
            "Memos": [
                {
                    "Memo": {
                        "MemoData": memo_hex,
                        "MemoType": bytes("text/plain", "utf-8").hex().upper(),
                    }
                }
            ],
        },
        "options": {
            "expire": 5,  # expires in 5 minutes
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{XAMAN_API_URL}/payload",
            json=payload,
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

    return {
        "payloadId": data["uuid"],
        "qrUrl": data["refs"]["qr_png"],
        "deepLink": data["next"]["always"],
        "expiresAt": data.get("refs", {}).get("expires_at"),
    }


async def get_payload_status(payload_id: str) -> dict:
    '''
    Check whether a Xaman payment request has been signed.

    Returns the payload status including whether it was signed,
    rejected, or is still pending.
    '''
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{XAMAN_API_URL}/payload/{payload_id}",
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

    meta = data.get("meta", {})
    res = data.get("response", {})

    return {
        "payloadId": payload_id,
        "signed": meta.get("signed", False),
        "rejected": meta.get("cancelled", False) or meta.get("expired", False),
        "expired": meta.get("expired", False),
        "txHash": res.get("txid"),
        "account": res.get("account"),
        "resolvedAt": meta.get("resolved_at"),
    }
