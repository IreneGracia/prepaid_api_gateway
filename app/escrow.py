import os
import time

from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import EscrowFinish, EscrowCancel
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet

load_dotenv()

'''
XRPL Escrow operations.

Instead of receiving XRP directly (which makes the gateway a custodian),
we use XRPL escrows:

- User creates an escrow that locks XRP on the XRPL itself
- The gateway provisions credits based on the locked amount
- As credits are consumed, the gateway claims from the escrow (EscrowFinish)
- If the user wants unused credits back, the escrow can be cancelled (EscrowCancel)

The gateway never holds user funds — the XRPL does.
'''

XRPL_RPC = os.getenv("XRPL_RPC", "https://s.altnet.rippletest.net:51234")
XRPL_RECEIVER_SEED = os.getenv("XRPL_RECEIVER_SEED", "")


def _get_wallet():
    '''Load the gateway's XRPL wallet from the seed in .env.'''
    if not XRPL_RECEIVER_SEED:
        raise RuntimeError("XRPL_RECEIVER_SEED not configured")
    return Wallet.from_seed(XRPL_RECEIVER_SEED)


def finish_escrow(sender_address: str, escrow_sequence: int,
                  condition: str = None, fulfillment: str = None) -> dict:
    '''
    Claim an escrow (EscrowFinish) — releases the locked XRP to the gateway.

    This is called when credits have been consumed and the gateway
    is entitled to claim the corresponding XRP.

    Args:
        sender_address: the XRPL address that created the escrow
        escrow_sequence: the sequence number of the EscrowCreate transaction
        condition: optional crypto-condition (hex)
        fulfillment: optional fulfillment for the condition (hex)
    '''
    wallet = _get_wallet()
    client = JsonRpcClient(XRPL_RPC)

    tx = EscrowFinish(
        account=wallet.address,
        owner=sender_address,
        offer_sequence=escrow_sequence,
        **({"condition": condition, "fulfillment": fulfillment}
           if condition and fulfillment else {}),
    )

    result = submit_and_wait(tx, client, wallet)
    tx_result = result.result

    return {
        "success": tx_result.get("meta", {}).get("TransactionResult") == "tesSUCCESS",
        "txHash": tx_result.get("hash"),
    }


def cancel_escrow_on_ledger(sender_address: str, escrow_sequence: int) -> dict:
    '''
    Cancel an escrow (EscrowCancel) — returns the locked XRP to the sender.

    This can only succeed if the cancel_after time has passed.
    Used when a user wants to reclaim unused credits.

    Args:
        sender_address: the XRPL address that created the escrow
        escrow_sequence: the sequence number of the EscrowCreate transaction
    '''
    wallet = _get_wallet()
    client = JsonRpcClient(XRPL_RPC)

    tx = EscrowCancel(
        account=wallet.address,
        owner=sender_address,
        offer_sequence=escrow_sequence,
    )

    result = submit_and_wait(tx, client, wallet)
    tx_result = result.result

    return {
        "success": tx_result.get("meta", {}).get("TransactionResult") == "tesSUCCESS",
        "txHash": tx_result.get("hash"),
    }
