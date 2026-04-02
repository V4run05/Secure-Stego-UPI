"""
core/crypto.py
Cryptographic primitives used by both the standalone stego pipeline
and the UPI transaction layer.
"""

import hashlib
import hmac
import os
import struct
from dataclasses import dataclass

import torch
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

NOISE_DIM    = 100   # must match Config.noise_dim
PAYLOAD_BITS = 256   # must match Config.payload_bits


# ─────────────────────────────────────────────────────────────────────────────
#  Key derivation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CryptoKeys:
    aes_key:   bytes   # 16 bytes
    prng_seed: int     # 64-bit int, seeds the noise vector


def derive_keys(password: str, salt: bytes | None = None) -> tuple["CryptoKeys", bytes]:
    """
    PBKDF2-HMAC-SHA256 → AES-128 key + PRNG seed.

    Returns (CryptoKeys, salt). Pass salt=<existing> on the decode side.
    """
    if salt is None:
        salt = os.urandom(16)
    raw = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=24)
    return CryptoKeys(aes_key=raw[:16], prng_seed=struct.unpack(">Q", raw[16:24])[0]), salt


# ─────────────────────────────────────────────────────────────────────────────
#  AES-128-CBC
# ─────────────────────────────────────────────────────────────────────────────

def aes_encrypt(plaintext: bytes, aes_key: bytes) -> bytes:
    """Encrypt raw bytes. Returns IV(16) + ciphertext."""
    iv     = os.urandom(16)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(pad(plaintext, AES.block_size))


def aes_decrypt(blob: bytes, aes_key: bytes) -> bytes:
    """Decrypt a blob produced by aes_encrypt(). Returns plaintext bytes."""
    cipher = AES.new(aes_key, AES.MODE_CBC, blob[:16])
    return unpad(cipher.decrypt(blob[16:]), AES.block_size)


def encrypt_message(message: str, keys: "CryptoKeys") -> bytes:
    """Encrypt a UTF-8 string. Returns IV + ciphertext."""
    return aes_encrypt(message.encode("utf-8"), keys.aes_key)


def decrypt_message(blob: bytes, keys: "CryptoKeys") -> str:
    """Decrypt a blob from encrypt_message(). Returns UTF-8 string."""
    try:
        return aes_decrypt(blob, keys.aes_key).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed — wrong password or corrupted data. ({e})")


# ─────────────────────────────────────────────────────────────────────────────
#  Bit tensor conversion
# ─────────────────────────────────────────────────────────────────────────────

def bytes_to_tensor(data: bytes, num_bits: int = PAYLOAD_BITS) -> torch.Tensor:
    """Convert bytes → float32 tensor of {0.0, 1.0}, padded/truncated to num_bits."""
    bits = []
    for byte in data:
        for bp in range(7, -1, -1):
            bits.append(float((byte >> bp) & 1))
    if len(bits) < num_bits:
        bits += [0.0] * (num_bits - len(bits))
    return torch.tensor(bits[:num_bits], dtype=torch.float32)


def tensor_to_bytes(tensor: torch.Tensor) -> bytes:
    """Convert a float32 bit-tensor back to bytes. Values ≥ 0.5 → 1."""
    bits = (tensor.detach().cpu() >= 0.5).int().tolist()
    out  = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | (bits[i + j] if i + j < len(bits) else 0)
        out.append(byte)
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────────
#  Deterministic noise vector
# ─────────────────────────────────────────────────────────────────────────────

def make_noise_vector(prng_seed: int, batch_size: int = 1,
                      device: torch.device | None = None) -> torch.Tensor:
    """
    Generate a reproducible noise vector from a seeded PRNG.

    Both sender and receiver call this with the same prng_seed (derived from
    the shared password) to get the identical z — this is what allows the
    Extractor to isolate the message component.
    """
    gen = torch.Generator()
    gen.manual_seed(prng_seed % (2 ** 32))
    z = torch.randn(batch_size, NOISE_DIM, generator=gen)
    return z.to(device) if device else z
