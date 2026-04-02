"""
upi/transaction.py
Transaction payload and compact token encoding/decoding.

Compact token layout (16 bytes = 1 AES-128 block):
    Bytes  0-5  : session_token  (6 bytes, random per transaction)
    Bytes  6-9  : tx_id_hash     (4 bytes, SHA-256[:4] of tx_id UUID)
    Bytes 10-13 : amount_cents   (4 bytes, uint32 big-endian)
    Bytes 14-15 : recipient_hash (2 bytes, SHA-256[:2] of recipient UPI ID)

After AES-128-CBC encryption: IV(16) + CT(16) = 32 bytes = 256 bits embedded.
"""

import hashlib
import hmac
import os
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TransactionStatus(Enum):
    PENDING_FACE = "pending_face"
    PENDING_PIN  = "pending_pin"
    AUTHORIZED   = "authorized"
    REJECTED     = "rejected"
    EXPIRED      = "expired"


@dataclass
class Transaction:
    tx_id:         str
    sender_upi:    str
    recipient_upi: str
    amount_rupees: float
    timestamp:     int
    status:        TransactionStatus = TransactionStatus.PENDING_FACE
    session_token: bytes = field(default_factory=lambda: os.urandom(6))
    auth_attempts: int = 0

    @property
    def amount_cents(self) -> int:
        return int(round(self.amount_rupees * 100))

    def is_expired(self, ttl_seconds: int = 300) -> bool:
        return (time.time() - self.timestamp) > ttl_seconds


@dataclass
class CompactToken:
    session_token:  bytes
    tx_id_hash:     bytes
    amount_cents:   int
    recipient_hash: bytes


# ─────────────────────────────────────────────────────────────────────────────
#  Encoding / decoding
# ─────────────────────────────────────────────────────────────────────────────

def _hash_field(value: str, n: int) -> bytes:
    return hashlib.sha256(value.encode()).digest()[:n]


def encode_compact_token(tx: Transaction) -> bytes:
    token = (tx.session_token
             + _hash_field(tx.tx_id, 4)
             + struct.pack(">I", tx.amount_cents)
             + _hash_field(tx.recipient_upi, 2))
    assert len(token) == 16
    return token


def decode_compact_token(raw: bytes) -> CompactToken:
    if len(raw) != 16:
        raise ValueError(f"Expected 16 bytes, got {len(raw)}")
    return CompactToken(
        session_token  = raw[0:6],
        tx_id_hash     = raw[6:10],
        amount_cents   = struct.unpack(">I", raw[10:14])[0],
        recipient_hash = raw[14:16],
    )


def verify_compact_token(token: CompactToken, tx: Transaction) -> tuple[bool, list[str]]:
    """Check that a decoded token matches the server-side transaction record."""
    failures = []
    if not hmac.compare_digest(token.tx_id_hash,     _hash_field(tx.tx_id, 4)):
        failures.append("tx_id hash mismatch (possible replay attack)")
    if token.amount_cents != tx.amount_cents:
        failures.append(f"Amount mismatch: image={token.amount_cents} paise vs DB={tx.amount_cents} paise")
    if not hmac.compare_digest(token.recipient_hash, _hash_field(tx.recipient_upi, 2)):
        failures.append("Recipient hash mismatch (possible MITM)")
    return (len(failures) == 0), failures


# ─────────────────────────────────────────────────────────────────────────────
#  Factory / formatting
# ─────────────────────────────────────────────────────────────────────────────

def create_transaction(sender_upi: str, recipient_upi: str,
                       amount_rupees: float) -> Transaction:
    MAX = 42_949_672.95
    if amount_rupees <= 0:
        raise ValueError("Amount must be positive")
    if amount_rupees > MAX:
        raise ValueError(f"Amount exceeds max encodable value ({MAX:.2f} INR)")
    return Transaction(
        tx_id         = str(uuid.uuid4()),
        sender_upi    = sender_upi,
        recipient_upi = recipient_upi,
        amount_rupees = amount_rupees,
        timestamp     = int(time.time()),
        session_token = os.urandom(6),
    )


def format_receipt(tx: Transaction) -> dict:
    return {
        "tx_id":         tx.tx_id,
        "sender_upi":    tx.sender_upi,
        "recipient_upi": tx.recipient_upi,
        "amount_rupees": round(tx.amount_rupees, 2),
        "timestamp":     tx.timestamp,
        "status":        tx.status.value,
    }
