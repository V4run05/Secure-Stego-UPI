"""
run_backend.py — Flask HTTP wrapper for SecureStego-UPI

Exposes the API endpoints consumed by the frontend:
  GET  /health
  POST /auth/register
  POST /transaction/initiate
  POST /transaction/verify
  GET  /transactions/list?user_id=...

Run:
    python run_backend.py

Listens on localhost:8000. The Vite dev server proxies /api/* here.
"""

import logging
import os

from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ── Lazy API loading (deferred so Flask starts even if ML deps are missing) ───

_api = None
_api_error: str | None = None


def get_api():
    global _api, _api_error
    if _api is not None:
        return _api
    try:
        from api import SecureStegoUPI  # noqa: PLC0415
        checkpoint = os.environ.get("CHECKPOINT_PATH", "checkpoints/checkpoint_final.pt")
        try:
            _api = SecureStegoUPI.from_checkpoint(
                checkpoint_path=checkpoint,
                app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"),
            )
            logger.info(f"Loaded checkpoint: {checkpoint}")
        except Exception as e:
            logger.warning(f"Checkpoint not found ({e}) — using untrained/demo mode")
            _api = SecureStegoUPI.untrained(
                app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"),
            )
        _api_error = None
        return _api
    except Exception as e:
        _api_error = str(e)
        logger.exception("Failed to initialise backend API")
        raise RuntimeError(f"Backend initialisation failed: {e}") from e


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    try:
        return jsonify(get_api().health()), 200
    except Exception as e:
        logger.exception("Health endpoint error")
        return jsonify({
            "status": "error",
            "error": str(e),
            "hint": "Backend ML dependencies may be missing (e.g. torch). Run: pip install -r requirements.txt",
        }), 503


@app.route("/auth/register", methods=["POST"])
def register():
    try:
        data = request.get_json(force=True, silent=True)
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
    except RuntimeError as e:
        logger.error(f"Register — backend unavailable: {e}")
        return jsonify({"success": False, "reason": str(e)}), 503
    except Exception as e:
        logger.exception("Register endpoint error")
        return jsonify({"success": False, "reason": f"Server error: {e}"}), 500


@app.route("/transaction/initiate", methods=["POST"])
def initiate():
    try:
        data = request.get_json(force=True, silent=True)
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
        if isinstance(result, dict) and "error" in result:
            return jsonify(result), 403
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        return jsonify(result), 200
    except RuntimeError as e:
        logger.error(f"Initiate — backend unavailable: {e}")
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        logger.exception("Initiate endpoint error")
        return jsonify({"error": f"Server error: {e}"}), 500


@app.route("/transaction/verify", methods=["POST"])
def verify():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"authorized": False, "reason": "No JSON body"}), 400
        tx_id      = data.get("tx_id", "").strip()
        pin_digits = data.get("pin_digits", {})
        if not tx_id or not pin_digits:
            return jsonify({"authorized": False, "reason": "tx_id and pin_digits are required"}), 400
        result = get_api().verify_transaction(tx_id, pin_digits)
        if hasattr(result, "to_dict"):
            result = result.to_dict()
        status = 200 if result.get("authorized") else 403
        return jsonify(result), status
    except RuntimeError as e:
        logger.error(f"Verify — backend unavailable: {e}")
        return jsonify({"authorized": False, "reason": str(e)}), 503
    except Exception as e:
        logger.exception("Verify endpoint error")
        return jsonify({"authorized": False, "reason": f"Server error: {e}"}), 500


@app.route("/transactions/list", methods=["GET"])
def list_transactions():
    try:
        user_id = request.args.get("user_id", "").strip()
        if not user_id:
            return jsonify({"error": "user_id query param required"}), 400
        txs = get_api()._p.db.get_user_transactions(user_id)
        return jsonify({"transactions": txs}), 200
    except RuntimeError as e:
        logger.error(f"List transactions — backend unavailable: {e}")
        return jsonify({"error": str(e), "transactions": []}), 503
    except Exception as e:
        logger.exception("List transactions endpoint error")
        return jsonify({"error": f"Server error: {e}", "transactions": []}), 500


# ── Entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", 8000))
    logger.info(f"Backend starting on localhost:{port}")
    app.run(
        host="localhost",
        port=port,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        use_reloader=False,
    )
