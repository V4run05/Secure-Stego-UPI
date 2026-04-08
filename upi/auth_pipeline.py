"""
upi/auth_pipeline.py
Full SecureStego-UPI authentication pipeline.

Orchestrates:
    register_user()         — store PIN hash + face embedding + registration MACs
    initiate_transaction()  — face auth → stego encode → PIN challenge
    verify_transaction()    — dynamic PIN verify → authorize/reject
"""

import base64
import logging
import time
from dataclasses import dataclass

from core.config import Config
from core.models import Generator, Extractor
from upi.database import DatabaseManager
from upi.transaction import (
    Transaction, TransactionStatus, create_transaction,
    format_receipt,
)
from upi.face_auth import register_face, verify_face
from upi.dynamic_pin import (
    validate_pin_format, hash_pin,
    build_registration_macs, generate_challenge,
)
from upi.stego_bridge import encode_transaction, image_to_b64

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RegisterResult:
    success: bool
    user_id: str
    reason:  str
    def to_dict(self): return {"success": self.success, "user_id": self.user_id, "reason": self.reason}


@dataclass
class InitiateResult:
    tx_id:           str
    stego_image_b64: str
    salt_b64:        str
    pin_positions:   list[int]
    amount_rupees:   float
    recipient_upi:   str
    def to_dict(self):
        return {"tx_id": self.tx_id, "stego_image_b64": self.stego_image_b64,
                "salt_b64": self.salt_b64, "pin_positions": self.pin_positions,
                "amount_rupees": self.amount_rupees, "recipient_upi": self.recipient_upi}


@dataclass
class VerifyResult:
    authorized:         bool
    receipt:            dict | None
    reason:             str
    attempts_remaining: int
    def to_dict(self):
        return {"authorized": self.authorized, "receipt": self.receipt,
                "reason": self.reason, "attempts_remaining": self.attempts_remaining}


# ─────────────────────────────────────────────────────────────────────────────
#  AuthPipeline
# ─────────────────────────────────────────────────────────────────────────────

class AuthPipeline:
    """
    Full authentication pipeline. Instantiate once; reuse for all requests.

    Args:
        cfg:        Config instance.
        db:         DatabaseManager instance.
        G:          Trained Generator (eval mode).
        E:          Trained Extractor (eval mode).
        app_secret: Server-side secret. Store in an environment variable — never hardcode.
    """

    def __init__(self, cfg: Config, db: DatabaseManager,
                 G: Generator, E: Extractor, app_secret: str) -> None:
        self.cfg        = cfg
        self.db         = db
        self.G          = G
        self.E          = E
        self.app_secret = app_secret
        G.eval(); E.eval()

    def _stego_password(self, user_id: str) -> str:
        """Per-user stego encoding password derived from server secret + user_id."""
        import hashlib
        return hashlib.sha256(f"{self.app_secret}:{user_id}".encode()).hexdigest()

    # ── registration ─────────────────────────────────────────────────────────

    def register_user(self, user_id: str, face_image_b64: str, pin: str) -> RegisterResult:
        """
        Register a new user.
        Stores: bcrypt PIN hash, face embedding, per-position registration MACs.
        """
        try:
            validate_pin_format(pin)
            if self.db.get_user(user_id):
                self.db.add_audit_log("REGISTER", "FAILURE", user_id=user_id,
                                       details="User already registered")
                return RegisterResult(False, user_id, f"Already registered: {user_id}")

            pin_hash = hash_pin(pin)
            reg_macs = build_registration_macs(pin, user_id, self.app_secret)
            self.db.create_user(user_id, pin_hash, pin_length=len(pin))
            self.db.store_registration_macs(user_id, reg_macs)
            register_face(user_id, face_image_b64, self.db)

            self.db.add_audit_log("REGISTER", "SUCCESS", user_id=user_id,
                                   details=f"PIN length: {len(pin)}")
            logger.info(f"Registered: {user_id}")
            return RegisterResult(True, user_id, "Registration successful")

        except Exception as e:
            self.db.add_audit_log("REGISTER", "ERROR", user_id=user_id,
                                   details="Registration exception")
            logger.error(f"Registration error for {user_id}: {e}")
            return RegisterResult(False, user_id, str(e))

    # ── initiate transaction (Layer 1) ────────────────────────────────────────

    def initiate_transaction(self, user_id: str, face_image_b64: str,
                              amount_rupees: float, recipient_upi: str) -> "InitiateResult | dict":
        """
        Step 1 of 2: verify face, generate stego image, return PIN challenge.

        Returns InitiateResult on success, or {"error": str} on failure.
        """
        user = self.db.get_user(user_id)
        if not user:
            self.db.add_audit_log("TX_INITIATE", "FAILURE", user_id=user_id,
                                   details="User not registered")
            return {"error": f"User not registered: {user_id}"}

        if self.db.is_user_locked(user_id):
            self.db.add_audit_log("TX_INITIATE", "FAILURE", user_id=user_id,
                                   details="Account locked")
            return {"error": "Account locked. Try again later.", "attempts_remaining": 0}

        # ── Layer 1: Face auth ────────────────────────────────────────────────
        face_result = verify_face(user_id, face_image_b64, self.db)
        if not face_result.passed:
            attempts = self.db.increment_failed_attempts(user_id, self.cfg.max_auth_attempts)
            remaining = max(0, self.cfg.max_auth_attempts - attempts)
            self.db.add_audit_log("FACE_AUTH", "FAILURE", user_id=user_id,
                                   details=f"Reason: {face_result.reason}; remaining: {remaining}")
            if remaining == 0:
                self.db.add_audit_log("ACCOUNT_LOCK", "SUCCESS", user_id=user_id,
                                       details="Locked after max face auth failures")
            return {"error": f"Face auth failed: {face_result.reason}",
                    "attempts_remaining": remaining}

        self.db.add_audit_log("FACE_AUTH", "SUCCESS", user_id=user_id)
        self.db.reset_failed_attempts(user_id)

        # ── Create transaction ────────────────────────────────────────────────
        try:
            tx = create_transaction(user_id, recipient_upi, amount_rupees)
        except ValueError as e:
            self.db.add_audit_log("TX_INITIATE", "ERROR", user_id=user_id,
                                   details=str(e))
            return {"error": str(e)}

        tx.status = TransactionStatus.PENDING_PIN
        self.db.save_transaction(tx)

        # ── GAN stego encode ──────────────────────────────────────────────────
        password = self._stego_password(user_id)
        img, salt = encode_transaction(tx, password, self.cfg, self.G)

        # ── Dynamic PIN challenge ─────────────────────────────────────────────
        positions = generate_challenge(
            session_token = tx.session_token,
            tx_id         = tx.tx_id,
            pin_length    = user["pin_length"],
            num_positions = self.cfg.pin_challenge_count,
        )

        reg_macs = self.db.load_registration_macs(user_id)
        if reg_macs is None:
            logger.error(f"No registration MACs for {user_id}")
            self.db.add_audit_log("TX_INITIATE", "ERROR", user_id=user_id,
                                   tx_id=tx.tx_id, details="Missing registration MACs")
            return {"error": "User registration incomplete. Please re-register."}

        expected_macs = {pos: self._tx_mac_from_reg(reg_macs[pos], tx.tx_id)
                         for pos in positions if pos in reg_macs}

        self.db.save_pin_session(tx.tx_id, positions, expected_macs,
                                  ttl_seconds=self.cfg.session_ttl_seconds)

        self.db.add_audit_log("TX_INITIATE", "SUCCESS", user_id=user_id,
                               tx_id=tx.tx_id,
                               details=f"recipient={recipient_upi} amount={amount_rupees:.2f}")
        logger.info(f"TX initiated: {tx.tx_id} | {user_id} → {recipient_upi} | INR {amount_rupees:.2f}")

        return InitiateResult(
            tx_id            = tx.tx_id,
            stego_image_b64  = image_to_b64(img),
            salt_b64         = base64.b64encode(salt).decode(),
            pin_positions    = positions,
            amount_rupees    = amount_rupees,
            recipient_upi    = recipient_upi,
        )

    def _tx_mac_from_reg(self, reg_mac: bytes, tx_id: str) -> bytes:
        """HMAC(registration_mac, tx_id) — binds the expected MAC to this transaction."""
        import hmac, hashlib
        return hmac.new(reg_mac, tx_id.encode(), hashlib.sha256).digest()

    # ── verify transaction (Layer 2) ──────────────────────────────────────────

    def verify_transaction(self, tx_id: str,
                            submitted_digits: dict[int, str]) -> VerifyResult:
        """
        Step 2 of 2: verify dynamic PIN digits and authorize the transaction.
        """
        tx = self.db.load_transaction(tx_id)
        if not tx:
            return VerifyResult(False, None, "Transaction not found", 0)

        if tx.is_expired(self.cfg.session_ttl_seconds):
            tx.status = TransactionStatus.EXPIRED
            self.db.save_transaction(tx)
            self.db.add_audit_log("TX_VERIFY", "FAILURE", user_id=tx.sender_upi,
                                   tx_id=tx_id, details="Transaction expired")
            return VerifyResult(False, None, "Transaction expired", 0)

        if tx.status != TransactionStatus.PENDING_PIN:
            return VerifyResult(False, None, f"Invalid state: {tx.status.value}", 0)

        session = self.db.load_pin_session(tx_id)
        if not session:
            self.db.add_audit_log("TX_VERIFY", "FAILURE", user_id=tx.sender_upi,
                                   tx_id=tx_id, details="PIN session not found or expired")
            return VerifyResult(False, None, "PIN session not found or expired", 0)
        positions, expected_macs = session

        user = self.db.get_user(tx.sender_upi)
        if not user:
            return VerifyResult(False, None, "User not found", 0)

        if self.db.is_user_locked(tx.sender_upi):
            return VerifyResult(False, None, "Account locked. Try again later.", 0)

        submitted_macs = {}
        for pos in positions:
            digit = submitted_digits.get(pos, "")
            if not (digit.isdigit() and len(digit) == 1):
                return VerifyResult(False, None, f"Invalid digit at position {pos}",
                                    self.cfg.max_auth_attempts)
            submitted_macs[pos] = self._compute_submitted_mac(
                digit, pos, tx.sender_upi, tx_id
            )

        import hmac as _hmac
        all_ok = all(
            _hmac.compare_digest(expected_macs.get(pos, b"A"), submitted_macs.get(pos, b"B"))
            for pos in positions
        )

        if all_ok:
            tx.status = TransactionStatus.AUTHORIZED
            self.db.save_transaction(tx)
            self.db.delete_pin_session(tx_id)
            self.db.reset_failed_attempts(tx.sender_upi)
            self.db.add_audit_log("TX_VERIFY", "SUCCESS", user_id=tx.sender_upi,
                                   tx_id=tx_id, details="Transaction authorized")
            logger.info(f"Authorized: {tx_id}")
            return VerifyResult(True, format_receipt(tx),
                                "Transaction authorized", self.cfg.max_auth_attempts)
        else:
            tx.auth_attempts += 1
            attempts  = self.db.increment_failed_attempts(tx.sender_upi, self.cfg.max_auth_attempts)
            remaining = max(0, self.cfg.max_auth_attempts - attempts)
            self.db.add_audit_log("TX_VERIFY", "FAILURE", user_id=tx.sender_upi,
                                   tx_id=tx_id,
                                   details=f"Incorrect PIN; remaining={remaining}")
            if remaining == 0:
                tx.status = TransactionStatus.REJECTED
                self.db.save_transaction(tx)
                self.db.delete_pin_session(tx_id)
                self.db.add_audit_log("ACCOUNT_LOCK", "SUCCESS", user_id=tx.sender_upi,
                                       tx_id=tx_id, details="Locked after max PIN failures")
            logger.warning(f"PIN failed: {tx_id}")
            return VerifyResult(False, None, "Incorrect PIN digit(s)", remaining)

    def _compute_submitted_mac(self, digit: str, pos: int,
                                user_id: str, tx_id: str) -> bytes:
        """
        Recompute the tx-bound MAC for a submitted digit.
        Chain: HMAC(pos_key, digit) → HMAC(that, tx_id).
        """
        import hmac, hashlib
        from upi.dynamic_pin import _position_key
        pos_key  = _position_key(self.app_secret, user_id, pos)
        reg_mac  = hmac.new(pos_key, digit.encode(), hashlib.sha256).digest()
        return hmac.new(reg_mac, tx_id.encode(), hashlib.sha256).digest()
