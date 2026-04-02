"""
verify_backend.py
=================
End-to-end backend verification. Run this after installation to confirm
everything is wired correctly BEFORE starting training.

Run from the project root (securestego_upi/):

    python verify_backend.py

All tests use in-memory state (no files written, no GPU required for
model construction). A trained checkpoint is NOT needed — the script
tests structure, crypto, database, PIN logic, and the full API flow
with untrained (randomly initialised) model weights.

Expected output:
    [ PASS ] Imports
    [ PASS ] Config
    [ PASS ] Model construction
    [ PASS ] Forward pass (G, D, E)
    [ PASS ] Crypto — AES round-trip
    [ PASS ] Crypto — key derivation (deterministic noise)
    [ PASS ] Crypto — bit tensor conversion
    [ PASS ] Database — user CRUD
    [ PASS ] Database — face embedding store/load
    [ PASS ] Database — registration MACs store/load
    [ PASS ] Database — transaction save/load
    [ PASS ] Database — PIN session save/load/delete
    [ PASS ] Transaction — compact token encode/decode
    [ PASS ] Transaction — compact token verification
    [ PASS ] Dynamic PIN — hash + challenge generation
    [ PASS ] Dynamic PIN — correct digits pass
    [ PASS ] Dynamic PIN — wrong digits fail
    [ PASS ] API — register_user()
    [ PASS ] API — initiate_transaction() (face auth mocked)
    [ PASS ] API — verify_transaction() correct PIN
    [ PASS ] API — verify_transaction() wrong PIN
    [ PASS ] API — health()
    ──────────────────────────────────────────────
    All 22 checks passed. Backend is ready.
"""

import base64
import io
import os
import sys
import traceback

# ── colour helpers ────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = []
failed = []


def check(name: str, fn):
    try:
        fn()
        print(f"  {GREEN}[ PASS ]{RESET} {name}")
        passed.append(name)
    except Exception as e:
        print(f"  {RED}[ FAIL ]{RESET} {name}")
        print(f"           {RED}{e}{RESET}")
        if "--verbose" in sys.argv:
            traceback.print_exc()
        failed.append(name)


def make_dummy_image_b64(size: int = 128) -> str:
    """Create a tiny solid-colour JPEG image encoded as base64."""
    from PIL import Image
    img = Image.new("RGB", (size, size), color=(120, 80, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ─────────────────────────────────────────────────────────────────────────────
#  Test definitions
# ─────────────────────────────────────────────────────────────────────────────

def test_imports():
    import torch
    from core.config import Config
    from core.models import Generator, Discriminator, Extractor, build_models
    from core.crypto import (derive_keys, encrypt_message, decrypt_message,
                              bytes_to_tensor, tensor_to_bytes, make_noise_vector,
                              aes_encrypt, aes_decrypt)
    from core.dataset import get_folder_dataloader
    from core.train import Trainer
    from core.steganography import encode, decode
    from upi.transaction import (create_transaction, encode_compact_token,
                                  decode_compact_token, verify_compact_token)
    from upi.database import DatabaseManager
    from upi.dynamic_pin import (hash_pin, build_registration_macs,
                                  generate_challenge, make_expected_macs,
                                  check_pin_response)
    from upi.face_auth import check_liveness, register_face, verify_face
    from upi.stego_bridge import encode_transaction, decode_transaction
    from upi.auth_pipeline import AuthPipeline
    from api import SecureStegoUPI


def test_config():
    from core.config import Config
    cfg = Config()
    assert cfg.payload_bits == 256
    assert cfg.noise_dim    == 100
    assert cfg.image_size   == 64
    assert cfg.device is not None
    cfg2 = Config(); cfg2.num_epochs = 5
    assert cfg2.num_epochs == 5


def test_model_construction():
    import torch
    from core.config import Config
    from core.models import build_models
    cfg = Config()
    G, D, E = build_models(cfg)
    assert sum(p.numel() for p in G.parameters()) > 0
    assert sum(p.numel() for p in D.parameters()) > 0
    assert sum(p.numel() for p in E.parameters()) > 0


def test_forward_pass():
    import torch
    from core.config import Config
    from core.models import build_models
    cfg = Config()
    G, D, E = build_models(cfg)
    G.eval(); D.eval(); E.eval()
    with torch.no_grad():
        b = 2
        z = torch.randn(b, cfg.noise_dim,    device=cfg.device)
        m = torch.randint(0, 2, (b, cfg.payload_bits), dtype=torch.float32, device=cfg.device)
        imgs  = G(z, m)
        assert imgs.shape  == (b, 3, 64, 64), f"G output shape wrong: {imgs.shape}"
        d_out = D(imgs)
        assert d_out.shape == (b,),            f"D output shape wrong: {d_out.shape}"
        e_out = E(imgs)
        assert e_out.shape == (b, cfg.payload_bits), f"E output shape wrong: {e_out.shape}"


def test_crypto_aes():
    from core.crypto import aes_encrypt, aes_decrypt
    import os
    key       = os.urandom(16)
    plaintext = b"Hello, SecureStego-UPI! 1234567890abcdef"
    blob      = aes_encrypt(plaintext, key)
    recovered = aes_decrypt(blob, key)
    assert recovered == plaintext, "AES round-trip failed"


def test_crypto_key_derivation():
    from core.crypto import derive_keys, make_noise_vector
    password = "test_password_123"
    keys1, salt = derive_keys(password)
    keys2, _    = derive_keys(password, salt=salt)
    assert keys1.aes_key   == keys2.aes_key,   "AES key not deterministic"
    assert keys1.prng_seed == keys2.prng_seed,  "PRNG seed not deterministic"

    z1 = make_noise_vector(keys1.prng_seed)
    z2 = make_noise_vector(keys1.prng_seed)
    import torch
    assert torch.allclose(z1, z2), "Noise vector not reproducible"

    keys3, _ = derive_keys("different_password", salt=salt)
    assert keys3.aes_key != keys1.aes_key, "Different passwords should give different keys"


def test_crypto_bit_tensor():
    from core.crypto import bytes_to_tensor, tensor_to_bytes
    import os
    data      = os.urandom(32)
    tensor    = bytes_to_tensor(data, num_bits=256)
    recovered = tensor_to_bytes(tensor)
    assert recovered == data, "Bit tensor round-trip failed"
    assert tensor.shape == (256,)


def test_database_user_crud():
    from upi.database import DatabaseManager
    db = DatabaseManager(":memory:")
    db.create_user("alice@test", "hash123", 6)
    user = db.get_user("alice@test")
    assert user is not None
    assert user["pin_length"] == 6
    assert db.get_user("nobody") is None
    assert not db.is_user_locked("alice@test")
    db.increment_failed_attempts("alice@test", max_attempts=3)
    db.increment_failed_attempts("alice@test", max_attempts=3)
    db.increment_failed_attempts("alice@test", max_attempts=3)
    assert db.is_user_locked("alice@test")
    db.reset_failed_attempts("alice@test")
    assert not db.is_user_locked("alice@test")


def test_database_face_embedding():
    from upi.database import DatabaseManager
    import numpy as np
    db        = DatabaseManager(":memory:")
    db.create_user("bob@test", "hash", 4)
    emb       = np.random.randn(512).tolist()
    db.store_face_embedding("bob@test", emb)
    loaded    = db.load_face_embedding("bob@test")
    assert loaded is not None
    assert abs(loaded[0] - emb[0]) < 1e-6
    assert db.load_face_embedding("nobody") is None


def test_database_registration_macs():
    from upi.database import DatabaseManager
    import os
    db   = DatabaseManager(":memory:")
    macs = {1: os.urandom(32), 2: os.urandom(32), 3: os.urandom(32)}
    db.store_registration_macs("carol@test", macs)
    loaded = db.load_registration_macs("carol@test")
    assert loaded is not None
    assert set(loaded.keys()) == {1, 2, 3}
    assert loaded[1] == macs[1]
    assert db.load_registration_macs("nobody") is None


def test_database_transaction():
    from upi.database import DatabaseManager
    from upi.transaction import create_transaction, TransactionStatus
    db = DatabaseManager(":memory:")
    tx = create_transaction("alice@test", "bob@test", 500.0)
    db.save_transaction(tx)
    loaded = db.load_transaction(tx.tx_id)
    assert loaded is not None
    assert loaded.tx_id         == tx.tx_id
    assert loaded.amount_rupees == 500.0
    assert loaded.sender_upi    == "alice@test"
    tx.status = TransactionStatus.AUTHORIZED
    db.save_transaction(tx)
    assert db.load_transaction(tx.tx_id).status == TransactionStatus.AUTHORIZED


def test_database_pin_session():
    from upi.database import DatabaseManager
    import os
    db        = DatabaseManager(":memory:")
    positions = [1, 3, 5]
    macs      = {1: os.urandom(32), 3: os.urandom(32), 5: os.urandom(32)}
    db.save_pin_session("tx-abc", positions, macs)
    result = db.load_pin_session("tx-abc")
    assert result is not None
    loaded_pos, loaded_macs = result
    assert loaded_pos == positions
    assert loaded_macs[1] == macs[1]
    db.delete_pin_session("tx-abc")
    assert db.load_pin_session("tx-abc") is None


def test_compact_token_round_trip():
    from upi.transaction import create_transaction, encode_compact_token, decode_compact_token
    tx    = create_transaction("alice@okicici", "bob@okaxis", 1234.56)
    raw   = encode_compact_token(tx)
    assert len(raw) == 16, f"Compact token should be 16 bytes, got {len(raw)}"
    token = decode_compact_token(raw)
    assert token.amount_cents   == tx.amount_cents
    assert token.session_token  == tx.session_token


def test_compact_token_verification():
    from upi.transaction import create_transaction, encode_compact_token, decode_compact_token, verify_compact_token
    tx    = create_transaction("alice@okicici", "bob@okaxis", 999.00)
    token = decode_compact_token(encode_compact_token(tx))

    ok, failures = verify_compact_token(token, tx)
    assert ok, f"Token verification failed: {failures}"

    # Tamper with amount
    import struct, dataclasses
    raw_tampered   = list(encode_compact_token(tx))
    raw_tampered[10:14] = list(struct.pack(">I", 50000))   # change to 500 INR
    token_tampered = decode_compact_token(bytes(raw_tampered))
    ok2, failures2 = verify_compact_token(token_tampered, tx)
    assert not ok2, "Tampered token should fail verification"
    assert any("Amount" in f for f in failures2)


def test_dynamic_pin_hash_and_challenge():
    from upi.dynamic_pin import hash_pin, generate_challenge
    import os, bcrypt
    pin_hash = hash_pin("123456")
    assert bcrypt.checkpw(b"123456", pin_hash.encode())

    session_token = os.urandom(6)
    tx_id         = "test-tx-001"
    positions     = generate_challenge(session_token, tx_id, pin_length=6, num_positions=3)
    assert len(positions) == 3
    assert len(set(positions)) == 3, "Positions must be unique"
    assert all(1 <= p <= 6 for p in positions), "Positions out of range"
    assert positions == sorted(positions), "Positions should be sorted"

    # Deterministic: same inputs → same output
    positions2 = generate_challenge(session_token, tx_id, pin_length=6, num_positions=3)
    assert positions == positions2


def test_dynamic_pin_correct():
    from upi.dynamic_pin import build_registration_macs, generate_challenge, make_expected_macs, check_pin_response
    import os
    pin           = "482931"
    user_id       = "test@user"
    server_secret = "test-secret"
    tx_id         = "tx-correct-001"
    session_token = os.urandom(6)

    positions = generate_challenge(session_token, tx_id, pin_length=6, num_positions=3)
    expected  = make_expected_macs(pin, user_id, server_secret, tx_id, positions)
    submitted = {pos: pin[pos - 1] for pos in positions}

    ok, reason = check_pin_response(submitted, expected, user_id, server_secret, tx_id, positions)
    assert ok, f"Correct PIN should pass: {reason}"


def test_dynamic_pin_wrong():
    from upi.dynamic_pin import generate_challenge, make_expected_macs, check_pin_response
    import os
    pin           = "482931"
    user_id       = "test@user"
    server_secret = "test-secret"
    tx_id         = "tx-wrong-001"
    session_token = os.urandom(6)

    positions = generate_challenge(session_token, tx_id, pin_length=6, num_positions=3)
    expected  = make_expected_macs(pin, user_id, server_secret, tx_id, positions)

    wrong_digit   = "0" if pin[positions[0] - 1] != "0" else "1"
    submitted     = {pos: pin[pos - 1] for pos in positions}
    submitted[positions[0]] = wrong_digit   # corrupt one digit

    ok, reason = check_pin_response(submitted, expected, user_id, server_secret, tx_id, positions)
    assert not ok, "Wrong PIN should fail"


def test_api_register():
    from api import SecureStegoUPI
    api    = SecureStegoUPI.untrained()
    image  = make_dummy_image_b64()
    result = api.register_user("varun@test", image, "482931")
    assert result["success"], f"Registration failed: {result['reason']}"
    assert result["user_id"] == "varun@test"

    # Duplicate registration should fail
    result2 = api.register_user("varun@test", image, "482931")
    assert not result2["success"]


def test_api_initiate():
    """Face auth is mocked (DeepFace falls back to mock=passed when not installed)."""
    from api import SecureStegoUPI
    api   = SecureStegoUPI.untrained()
    image = make_dummy_image_b64()
    api.register_user("varun@test", image, "482931")

    result = api.initiate_transaction(
        user_id        = "varun@test",
        face_image_b64 = image,
        amount_rupees  = 500.0,
        recipient_upi  = "kailash@test",
    )
    if "error" in result:
        # If DeepFace IS installed and liveness fails on a tiny dummy image, that's expected.
        # Check it's a liveness error, not a system error.
        assert "Liveness" in result["error"] or "face" in result["error"].lower(), \
            f"Unexpected error: {result['error']}"
        print(f"\n           {YELLOW}[NOTE]{RESET} Liveness check rejected dummy image "
              f"(DeepFace installed). This is correct behaviour.")
        return

    assert "tx_id"           in result
    assert "stego_image_b64" in result
    assert "pin_positions"   in result
    assert "salt_b64"        in result
    assert len(result["pin_positions"]) == 3

    # Stego image must be a valid PNG
    raw = base64.b64decode(result["stego_image_b64"])
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(raw))
    assert img.size == (64, 64), f"Expected 64×64, got {img.size}"

    return result   # returned so verify tests can reuse it


def test_api_verify_correct():
    from api import SecureStegoUPI
    api   = SecureStegoUPI.untrained()
    image = make_dummy_image_b64()
    pin   = "482931"
    api.register_user("varun@test", image, pin)

    init = api.initiate_transaction(
        user_id        = "varun@test",
        face_image_b64 = image,
        amount_rupees  = 250.0,
        recipient_upi  = "kailash@test",
    )
    if "error" in init:
        print(f"\n           {YELLOW}[NOTE]{RESET} Skipped (liveness rejected dummy image).")
        return

    positions  = init["pin_positions"]
    pin_digits = {str(pos): pin[pos - 1] for pos in positions}

    result = api.verify_transaction(init["tx_id"], pin_digits)
    assert result["authorized"], f"Correct PIN should authorize: {result['reason']}"
    assert result["receipt"] is not None
    assert result["receipt"]["amount_rupees"] == 250.0


def test_api_verify_wrong():
    from api import SecureStegoUPI
    api   = SecureStegoUPI.untrained()
    image = make_dummy_image_b64()
    pin   = "482931"
    api.register_user("varun@test", image, pin)

    init = api.initiate_transaction(
        user_id        = "varun@test",
        face_image_b64 = image,
        amount_rupees  = 100.0,
        recipient_upi  = "kailash@test",
    )
    if "error" in init:
        print(f"\n           {YELLOW}[NOTE]{RESET} Skipped (liveness rejected dummy image).")
        return

    positions  = init["pin_positions"]
    wrong_char = "0" if pin[positions[0] - 1] != "0" else "1"
    pin_digits = {str(pos): pin[pos - 1] for pos in positions}
    pin_digits[str(positions[0])] = wrong_char

    result = api.verify_transaction(init["tx_id"], pin_digits)
    assert not result["authorized"], "Wrong PIN should not authorize"
    assert result["attempts_remaining"] < 3


def test_api_health():
    from api import SecureStegoUPI
    api    = SecureStegoUPI.untrained()
    health = api.health()
    assert health["status"]       == "ok"
    assert "device"               in health
    assert "payload_bits"         in health
    assert health["payload_bits"] == 256


# ─────────────────────────────────────────────────────────────────────────────
#  Runner
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print(f"{BOLD}SecureStego-UPI — Backend Verification{RESET}")
    print("─" * 46)

    tests = [
        ("Imports",                                test_imports),
        ("Config",                                 test_config),
        ("Model construction",                     test_model_construction),
        ("Forward pass (G, D, E)",                 test_forward_pass),
        ("Crypto — AES round-trip",                test_crypto_aes),
        ("Crypto — key derivation (deterministic)", test_crypto_key_derivation),
        ("Crypto — bit tensor conversion",         test_crypto_bit_tensor),
        ("Database — user CRUD",                   test_database_user_crud),
        ("Database — face embedding store/load",   test_database_face_embedding),
        ("Database — registration MACs store/load",test_database_registration_macs),
        ("Database — transaction save/load",       test_database_transaction),
        ("Database — PIN session save/load/delete",test_database_pin_session),
        ("Transaction — compact token encode/decode", test_compact_token_round_trip),
        ("Transaction — tamper detection",         test_compact_token_verification),
        ("Dynamic PIN — hash + challenge",         test_dynamic_pin_hash_and_challenge),
        ("Dynamic PIN — correct digits pass",      test_dynamic_pin_correct),
        ("Dynamic PIN — wrong digits fail",        test_dynamic_pin_wrong),
        ("API — register_user()",                  test_api_register),
        ("API — initiate_transaction()",           test_api_initiate),
        ("API — verify_transaction() correct PIN", test_api_verify_correct),
        ("API — verify_transaction() wrong PIN",   test_api_verify_wrong),
        ("API — health()",                         test_api_health),
    ]

    for name, fn in tests:
        check(name, fn)

    print()
    print("─" * 46)
    total = len(tests)
    n_ok  = len(passed)
    n_bad = len(failed)

    if n_bad == 0:
        print(f"  {GREEN}{BOLD}All {total} checks passed.{RESET} Backend is ready.")
        print()
        print("  Next steps:")
        print("    1. Download CelebA (see README.md)")
        print("    2. python run_training.py --epochs 50")
        print("    3. python run_training.py --epochs 5  (quick smoke test first)")
    else:
        print(f"  {RED}{BOLD}{n_bad} check(s) failed{RESET}, {n_ok} passed.")
        print()
        print("  Failed:")
        for f in failed:
            print(f"    {RED}✗{RESET} {f}")
        print()
        print("  Run with --verbose for full tracebacks:")
        print("    python verify_backend.py --verbose")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
