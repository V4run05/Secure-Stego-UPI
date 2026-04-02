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
from typing import Any

from core.config import Config
from core.models import Generator, Extractor, build_models
from upi.database import DatabaseManager
from upi.transaction import (
    Transaction, TransactionStatus, create_transaction,
    format_receipt, verify_compact_token,
)
from upi.face_auth import register_face, verify_face
from upi.dynamic_pin import (
    validate_pin_format, hash_pin,
    build_registration_macs, generate_challenge,
    make_expected_macs, check_pin_response,
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
                return RegisterResult(False, user_id, f"Already registered: {user_id}")

            # 1. Hash PIN
            pin_hash = hash_pin(pin)

            # 2. Build registration MACs (requires plaintext PIN — only time we use it)
            reg_macs = build_registration_macs(pin, user_id, self.app_secret)

            # 3. Store user record
            self.db.create_user(user_id, pin_hash, pin_length=len(pin))

            # 4. Store registration MACs
            self.db.store_registration_macs(user_id, reg_macs)

            # 5. Store face embedding
            register_face(user_id, face_image_b64, self.db)

            logger.info(f"Registered: {user_id}")
            return RegisterResult(True, user_id, "Registration successful")

        except Exception as e:
            logger.error(f"Registration error for {user_id}: {e}")
            return RegisterResult(False, user_id, str(e))

    # ── initiate transaction (Layer 1) ────────────────────────────────────────

    def initiate_transaction(self, user_id: str, face_image_b64: str,
                              amount_rupees: float, recipient_upi: str) -> InitiateResult | dict:
        """
        Step 1 of 2: verify face, generate stego image, return PIN challenge.

        Returns InitiateResult on success, or {"error": str} on failure.
        """
        user = self.db.get_user(user_id)
        if not user:
            return {"error": f"User not registered: {user_id}"}
        if self.db.is_user_locked(user_id):
            return {"error": "Account locked. Try again later."}

        # ── Layer 1: Face auth ────────────────────────────────────────────────
        face_result = verify_face(user_id, face_image_b64, self.db)
        if not face_result.passed:
            attempts = self.db.increment_failed_attempts(user_id, self.cfg.max_auth_attempts)
            remaining = max(0, self.cfg.max_auth_attempts - attempts)
            return {"error": f"Face auth failed: {face_result.reason}",
                    "attempts_remaining": remaining}

        self.db.reset_failed_attempts(user_id)

        # ── Create transaction ────────────────────────────────────────────────
        try:
            tx = create_transaction(user_id, recipient_upi, amount_rupees)
        except ValueError as e:
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

        # Compute expected MACs for the correct digits at the challenged positions.
        # We need the plaintext PIN here — but we don't have it.
        # SOLUTION: we stored registration MACs = HMAC(pos_key, correct_digit).
        # make_expected_macs() re-derives using server_secret + tx_id.
        # The pipeline below uses check_pin_response() which only needs
        # server_secret, user_id, tx_id — not the plaintext PIN.
        #
        # We store the expected MACs now; at verification we recompute for
        # the submitted digit and compare. The expected MACs are effectively
        # HMAC(pos_key, correct_digit + tx_id). This is correct.
        #
        # To get expected MACs without the PIN: we need to derive them from
        # registration_macs. reg_macs[pos] = HMAC(pos_key, correct_digit).
        # expected_mac[pos] = HMAC(reg_macs[pos], tx_id).
        # At verification: submitted_mac[pos] = HMAC(HMAC(pos_key, submitted_digit), tx_id).
        # These match IFF submitted_digit == correct_digit.
        #
        # This is the correct two-layer HMAC approach.
        reg_macs = self.db.load_registration_macs(user_id)
        if reg_macs is None:
            logger.error(f"No registration MACs for {user_id}. Was register_user() called?")
            return {"error": "User registration incomplete. Please re-register."}

        # Build expected tx-bound MACs from registration MACs
        expected_macs = {pos: self._tx_mac_from_reg(reg_macs[pos], tx.tx_id)
                         for pos in positions if pos in reg_macs}

        self.db.save_pin_session(tx.tx_id, positions, expected_macs)

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

        Args:
            tx_id:            From InitiateResult.
            submitted_digits: {position: digit_char}, e.g. {1: "4", 3: "7", 5: "2"}.
        """
        tx = self.db.load_transaction(tx_id)
        if not tx:
            return VerifyResult(False, None, "Transaction not found", 0)
        if tx.is_expired(self.cfg.session_ttl_seconds):
            tx.status = TransactionStatus.EXPIRED
            self.db.save_transaction(tx)
            return VerifyResult(False, None, "Transaction expired", 0)
        if tx.status != TransactionStatus.PENDING_PIN:
            return VerifyResult(False, None, f"Invalid state: {tx.status.value}", 0)

        session = self.db.load_pin_session(tx_id)
        if not session:
            return VerifyResult(False, None, "PIN session not found or expired", 0)
        positions, expected_macs = session

        user = self.db.get_user(tx.sender_upi)
        if not user:
            return VerifyResult(False, None, "User not found", 0)

        reg_macs = self.db.load_registration_macs(tx.sender_upi)
        if reg_macs is None:
            return VerifyResult(False, None, "Registration MACs missing", 0)

        # Recompute expected tx-bound MACs from submitted digits
        # submitted_expected[pos] = HMAC(HMAC(pos_key, submitted_digit), tx_id)
        # We can't compute HMAC(pos_key, submitted_digit) directly because we
        # don't store pos_keys (only reg_macs which already embedded the correct digit).
        #
        # Final check: compare HMAC(reg_macs[pos], tx_id) — which was computed
        # at challenge time for the CORRECT digit — against what we'd get if we
        # reran build_registration_macs with the submitted digit.
        #
        # Since we can't rerun build_registration_macs (no server_secret in
        # this scope... wait, we DO have app_secret), let's use it:
        submitted_macs = {}
        for pos in positions:
            digit = submitted_digits.get(pos, "")
            if not (digit.isdigit() and len(digit) == 1):
                return VerifyResult(False, None, f"Invalid digit at position {pos}", self.cfg.max_auth_attempts)
            submitted_macs[pos] = self._compute_submitted_mac(
                digit, pos, tx.sender_upi, tx_id
            )

        import hmac as _hmac
        all_ok = True
        for pos in positions:
            exp = expected_macs.get(pos, b"A")
            got = submitted_macs.get(pos, b"B")
            if not _hmac.compare_digest(exp, got):
                all_ok = False

        if all_ok:
            tx.status = TransactionStatus.AUTHORIZED
            self.db.save_transaction(tx)
            self.db.delete_pin_session(tx_id)
            self.db.reset_failed_attempts(tx.sender_upi)
            logger.info(f"Authorized: {tx_id}")
            return VerifyResult(True, format_receipt(tx),
                                "Transaction authorized", self.cfg.max_auth_attempts)
        else:
            tx.auth_attempts += 1
            attempts  = self.db.increment_failed_attempts(tx.sender_upi, self.cfg.max_auth_attempts)
            remaining = max(0, self.cfg.max_auth_attempts - attempts)
            if remaining == 0:
                tx.status = TransactionStatus.REJECTED
                self.db.save_transaction(tx)
                self.db.delete_pin_session(tx_id)
            logger.warning(f"PIN failed: {tx_id}")
            return VerifyResult(False, None, "Incorrect PIN digit(s)", remaining)

    def _compute_submitted_mac(self, digit: str, pos: int,
                                user_id: str, tx_id: str) -> bytes:
        """
        Recompute the tx-bound MAC for a submitted digit.
        Matches the chain: HMAC(pos_key, digit) → HMAC(that, tx_id).
        """
        import hmac, hashlib
        from upi.dynamic_pin import _position_key
        pos_key  = _position_key(self.app_secret, user_id, pos)
        reg_mac  = hmac.new(pos_key, digit.encode(), hashlib.sha256).digest()
        return hmac.new(reg_mac, tx_id.encode(), hashlib.sha256).digest()
