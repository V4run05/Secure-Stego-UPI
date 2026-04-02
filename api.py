"""
api.py — PUBLIC API for SecureStego-UPI
========================================

Your teammate's ONLY import. Four methods, plain dict responses.

  from api import SecureStegoUPI
  api = SecureStegoUPI.from_checkpoint("checkpoints/checkpoint_final.pt",
                                        app_secret=os.environ["APP_SECRET"])

  # Before training, use untrained mode for UI development:
  api = SecureStegoUPI.untrained()

Endpoints to wire up:

  POST /auth/register
    Body : { "user_id", "face_image_b64", "pin" }
    Reply: { "success": bool, "user_id", "reason" }

  POST /transaction/initiate
    Body : { "user_id", "face_image_b64", "amount_rupees", "recipient_upi" }
    Reply: { "tx_id", "stego_image_b64", "salt_b64",
             "pin_positions": [1,3,5], "amount_rupees", "recipient_upi" }
          or { "error": str, "attempts_remaining": int }

  POST /transaction/verify
    Body : { "tx_id", "pin_digits": {"1":"4","3":"7","5":"2"} }
    Reply: { "authorized": bool, "receipt": {...}|null,
             "reason": str, "attempts_remaining": int }

  GET /health
    Reply: { "status":"ok", "device", "payload_bits", "cuda_available", "timestamp" }
"""

import os
import time
import logging
from typing import Any

import torch

from core.config import Config
from core.models import build_models
from upi.database import DatabaseManager
from upi.auth_pipeline import AuthPipeline, InitiateResult, VerifyResult, RegisterResult

logger = logging.getLogger(__name__)


class SecureStegoUPI:

    def __init__(self, pipeline: AuthPipeline, cfg: Config) -> None:
        self._p   = pipeline
        self._cfg = cfg

    # ── factories ────────────────────────────────────────────────────────────

    @classmethod
    def from_checkpoint(cls, checkpoint_path: str,
                        app_secret: str | None = None,
                        cfg: Config | None = None,
                        db_path: str = "securestego.db") -> "SecureStegoUPI":
        """
        Load from a trained checkpoint file.

        app_secret should come from an environment variable in production:
            app_secret = os.environ["APP_SECRET"]
        """
        cfg    = cfg or Config()
        secret = app_secret or os.environ.get("APP_SECRET", "dev-secret-change-in-production")
        if secret == "dev-secret-change-in-production":
            logger.warning("Using default APP_SECRET. Set APP_SECRET env var in production.")

        G, _, E = build_models(cfg)
        state   = torch.load(checkpoint_path, map_location=cfg.device, weights_only=True)
        G.load_state_dict(state["G"])
        E.load_state_dict(state["E"])

        db       = DatabaseManager(db_path)
        pipeline = AuthPipeline(cfg=cfg, db=db, G=G, E=E, app_secret=secret)
        logger.info(f"Loaded checkpoint: {checkpoint_path}")
        return cls(pipeline, cfg)

    @classmethod
    def untrained(cls, app_secret: str = "dev-secret",
                  cfg: Config | None = None,
                  db_path: str = ":memory:") -> "SecureStegoUPI":
        """
        Create an instance with random weights for frontend development.
        All API methods work; stego images look like noise until trained.
        """
        cfg      = cfg or Config()
        G, _, E  = build_models(cfg)
        db       = DatabaseManager(db_path)
        pipeline = AuthPipeline(cfg=cfg, db=db, G=G, E=E, app_secret=app_secret)
        return cls(pipeline, cfg)

    # ── public methods ───────────────────────────────────────────────────────

    def register_user(self, user_id: str, face_image_b64: str, pin: str) -> dict:
        return self._p.register_user(user_id, face_image_b64, pin).to_dict()

    def initiate_transaction(self, user_id: str, face_image_b64: str,
                              amount_rupees: float, recipient_upi: str) -> dict:
        result = self._p.initiate_transaction(user_id, face_image_b64, amount_rupees, recipient_upi)
        return result.to_dict() if isinstance(result, InitiateResult) else result

    def verify_transaction(self, tx_id: str, pin_digits: dict[str, str]) -> dict:
        """pin_digits keys can be strings ("1","3","5") or ints — both accepted."""
        int_digits = {int(k): str(v) for k, v in pin_digits.items()}
        return self._p.verify_transaction(tx_id, int_digits).to_dict()

    def health(self) -> dict:
        return {
            "status":         "ok",
            "device":         str(self._cfg.device),
            "payload_bits":   self._cfg.payload_bits,
            "image_size":     self._cfg.image_size,
            "cuda_available": torch.cuda.is_available(),
            "timestamp":      int(time.time()),
        }
