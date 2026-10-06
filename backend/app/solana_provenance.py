"""Devnet-only Memo publishing; external signing and real finalized receipts."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import httpx
from solders.hash import Hash
from solders.instruction import AccountMeta, Instruction
from solders.message import MessageV0
from solders.null_signer import NullSigner
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

MEMO_PROGRAM = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
DEVNET_GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
DEVNET_RPC = "https://api.devnet.solana.com"


class DevnetRPC:
    def __init__(self, transport=None):
        self.transport = transport

    def call(self, method, params=None):
        with httpx.Client(timeout=20, transport=self.transport) as client:
            response = client.post(
                DEVNET_RPC,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
            )
            response.raise_for_status()
            body = response.json()
        if body.get("error") or "result" not in body:
            raise ValueError("Devnet RPC rejected request; retry explicitly")
        return body["result"]

    def verify_network(self):
        if self.call("getGenesisHash") != DEVNET_GENESIS:
            raise ValueError("RPC genesis is not Solana devnet; publishing refused")


def build_unsigned(memo, publisher, blockhash):
    key = Pubkey.from_string(publisher)
    if len(memo.encode("utf-8")) > 450 or not memo.startswith("ORAKT1|"):
        raise ValueError("Invalid ORAKT memo")
    instruction = Instruction(
        Pubkey.from_string(MEMO_PROGRAM), memo.encode(), [AccountMeta(key, True, False)]
    )
    message = MessageV0.try_compile(key, [instruction], [], Hash.from_string(blockhash))
    return base64.b64encode(bytes(VersionedTransaction(message, [NullSigner(key)]))).decode()


def decode_transaction(encoded):
    if not isinstance(encoded, str) or len(encoded) > 2200:
        raise ValueError("Transaction exceeds bound")
    try:
        raw = base64.b64decode(encoded, validate=True)
        tx = VersionedTransaction.from_bytes(raw)
        tx.sanitize()
        return tx
    except Exception as exc:
        raise ValueError("Malformed Solana transaction") from exc


def validate_signed(encoded, unsigned, publisher):
    signed = decode_transaction(encoded)
    draft = decode_transaction(unsigned)
    if bytes(signed.message) != bytes(draft.message):
        raise ValueError("Signed transaction changed prepared message")
    if (
        len(signed.signatures) != 1
        or str(signed.message.account_keys[0]) != publisher
        or signed.message.header.num_required_signatures != 1
    ):
        raise ValueError("Publisher/signature mismatch")
    if not all(signed.verify_with_results()):
        raise ValueError("Invalid publisher signature")
    # Message was prepared by server; there can be no transfers/approvals hidden
    # alongside the one signed memo, even if a client tampers with request bytes.
    instructions = signed.message.instructions
    if (
        len(instructions) != 1
        or str(signed.message.account_keys[instructions[0].program_id_index]) != MEMO_PROGRAM
    ):
        raise ValueError("Only one Memo instruction is permitted")
    return str(signed.signatures[0])


def build_transaction(row, publisher, rpc):
    rpc.verify_network()
    if row.signature:
        raise ValueError("Already submitted: verify or retry the existing transaction")
    latest = rpc.call("getLatestBlockhash", [{"commitment": "finalized"}])["value"]
    row.publisher = publisher
    row.unsigned_transaction = build_unsigned(row.memo, publisher, latest["blockhash"])
    row.last_valid_block_height = latest["lastValidBlockHeight"]
    return {
        "transaction": row.unsigned_transaction,
        "publisher": publisher,
        "chain": "solana:devnet",
        "last_valid_block_height": row.last_valid_block_height,
        "memo": row.memo,
        "message": "Only a devnet fee and hash memo; no token transfer.",
    }


def submit(session, row, encoded, publisher, rpc):
    if not row.unsigned_transaction or row.publisher != publisher:
        raise ValueError("Prepare a transaction for the configured publisher first")
    signature = validate_signed(encoded, row.unsigned_transaction, publisher)
    if row.signature and row.signature != signature:
        raise ValueError("An immutable signed attempt already exists")
    if row.status == "finalized":
        return
    rpc.verify_network()
    # Store before network IO: an uncertain HTTP outcome is recoverable by
    # verifying/rebroadcasting the same signature, never signing another payment.
    row.signature = signature
    row.signed_transaction = encoded
    row.status = "submitted"
    session.commit()
    returned = rpc.call(
        "sendTransaction",
        [
            encoded,
            {
                "encoding": "base64",
                "skipPreflight": False,
                "preflightCommitment": "finalized",
                "maxRetries": 2,
            },
        ],
    )
    if returned != signature:
        raise ValueError("RPC signature mismatch; verify saved attempt")


def verify(row, rpc):
    if not row.signature or not row.signed_transaction:
        return {"state": "not_submitted"}
    rpc.verify_network()
    receipt = rpc.call(
        "getTransaction",
        [
            row.signature,
            {
                "commitment": "finalized",
                "encoding": "base64",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )
    if receipt is None:
        return {"state": "not_finalized", "note": "未找到最终确认，不能标记为已上链。"}
    meta = receipt.get("meta")
    if not isinstance(meta, dict) or "err" not in meta or meta["err"] is not None:
        return {"state": "execution_failed", "note": "交易未成功执行；不算有效存证。"}
    transaction = receipt.get("transaction")
    if not isinstance(transaction, list) or len(transaction) != 2 or transaction[1] != "base64":
        raise ValueError("Malformed RPC receipt")
    signature = validate_signed(transaction[0], row.unsigned_transaction, row.publisher)
    if signature != row.signature:
        raise ValueError("Receipt does not match saved transaction")
    if bytes(decode_transaction(transaction[0])) != bytes(
        decode_transaction(row.signed_transaction)
    ):
        raise ValueError("Receipt bytes mismatch")
    slot = receipt.get("slot")
    if not isinstance(slot, int) or isinstance(slot, bool) or slot < 0:
        raise ValueError("Invalid receipt slot")
    row.receipt = {
        "slot": slot,
        "block_time": receipt.get("blockTime"),
        "commitment": "finalized",
        "genesis_hash": DEVNET_GENESIS,
        "verified_at": datetime.now(UTC).isoformat(),
        "rpc": DEVNET_RPC,
    }
    row.status = "finalized"
    return {"state": "finalized", **row.receipt}
