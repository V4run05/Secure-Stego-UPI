"""
run_backend.py — Flask HTTP wrapper for SecureStego-UPI

Exposes the four API endpoints consumed by the frontend:
  GET  /health
  POST /auth/register
  POST /transaction/initiate
  POST /transaction/verify
  GET  /transactions/list?user_id=...

Run:
    python run_backend.py

The backend listens on localhost:8000 (never on port 5000 which is the frontend).
The Vite dev server proxies /api/* to this server, so the frontend calls /api/...
"""

import logging
import os

from flask import Flask, request, jsonify
from flask_cors import CORS

from api import SecureStegoUPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ── Load API ──────────────────────────────────────────────────────────────────

def _load_api() -> SecureStegoUPI:
    checkpoint = os.environ.get("CHECKPOINT_PATH", "checkpoints/checkpoint_final.pt")
    try:
        api = SecureStegoUPI.from_checkpoint(
            checkpoint_path=checkpoint,
            app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"),
        )
        logger.info(f"Loaded checkpoint: {checkpoint}")
        return api
    except Exception as e:
        logger.warning(f"Checkpoint not found ({e}) — starting in untrained/demo mode")
        return SecureStegoUPI.untrained(
            app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"),
        )


_api: SecureStegoUPI | None = None


def get_api() -> SecureStegoUPI:
    global _api
    if _api is None:
        _api = _load_api()
    return _api


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify(get_api().health())


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"success": False, "reason": "No JSON body"}), 400
    user_id        = data.get("user_id", "").strip()
    face_image_b64 = data.get("face_image_b64", "")
    pin            = data.get("pin", "")
    if not user_id or not pin:
        return jsonify({"success": False, "reason": "user_id and pin are required"}), 400
    result = get_api().register_user(user_id, face_image_b64, pin)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.route("/transaction/initiate", methods=["POST"])
def initiate():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400
    user_id        = data.get("user_id", "").strip()
    face_image_b64 = data.get("face_image_b64", "")
    amount_rupees  = data.get("amount_rupees")
    recipient_upi  = data.get("recipient_upi", "").strip()
    if not all([user_id, recipient_upi, amount_rupees is not None]):
        return jsonify({"error": "user_id, recipient_upi, amount_rupees are required"}), 400
    try:
        amount_rupees = float(amount_rupees)
    except (TypeError, ValueError):
        return jsonify({"error": "amount_rupees must be a number"}), 400
    result = get_api().initiate_transaction(user_id, face_image_b64, amount_rupees, recipient_upi)
    if "error" in result:
        return jsonify(result), 403
    return jsonify(result), 200


@app.route("/transaction/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"authorized": False, "reason": "No JSON body"}), 400
    tx_id      = data.get("tx_id", "").strip()
    pin_digits = data.get("pin_digits", {})
    if not tx_id or not pin_digits:
        return jsonify({"authorized": False, "reason": "tx_id and pin_digits are required"}), 400
    result = get_api().verify_transaction(tx_id, pin_digits)
    status = 200 if result.get("authorized") else 403
    return jsonify(result), status


@app.route("/transactions/list", methods=["GET"])
def list_transactions():
    user_id = request.args.get("user_id", "").strip()
    if not user_id:
        return jsonify({"error": "user_id query param required"}), 400
    txs = get_api()._p.db.get_user_transactions(user_id)
    return jsonify({"transactions": txs}), 200


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", 8000))
    logger.info(f"Backend starting on localhost:{port}")
    app.run(
        host="localhost",
        port=port,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )
