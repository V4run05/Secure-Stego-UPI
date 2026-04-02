"""
upi/stego_bridge.py
Connects the UPI transaction layer to the GAN steganography core.

encode_transaction: Transaction → stego PIL image
decode_transaction: stego PIL image → CompactToken (for tamper verification)
"""

import base64
import hashlib
import io
import os
import struct

import torch
from PIL import Image
from torchvision import transforms

from core.config import Config
from core.models import Generator, Extractor
from upi.transaction import Transaction, CompactToken, encode_compact_token, decode_compact_token

_IMG_TRANSFORM = transforms.Compose([
    transforms.Resize(64),
    transforms.CenterCrop(64),
    transforms.ToTensor(),
    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
])


def _derive_keys(password: str, salt: bytes) -> tuple[bytes, int]:
    raw  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=24)
    seed = struct.unpack(">Q", raw[16:24])[0]
    return raw[:16], seed


def _aes_encrypt(plaintext: bytes, key: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    iv = os.urandom(16)
    return iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(plaintext, 16))


def _aes_decrypt(blob: bytes, key: bytes) -> bytes:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    return unpad(AES.new(key, AES.MODE_CBC, blob[:16]).decrypt(blob[16:]), 16)


def _bytes_to_tensor(data: bytes, num_bits: int, device) -> torch.Tensor:
    bits = [float((b >> bp) & 1) for b in data for bp in range(7, -1, -1)]
    bits = bits[:num_bits] + [0.0] * max(0, num_bits - len(bits))
    return torch.tensor(bits, dtype=torch.float32, device=device)


def _tensor_to_bytes(t: torch.Tensor) -> bytes:
    bits = (t.detach().cpu() >= 0.5).int().tolist()
    return bytes((sum(bits[i+j] << (7-j) for j in range(8) if i+j < len(bits))
                  for i in range(0, len(bits), 8)))


def _tensor_to_pil(t: torch.Tensor) -> Image.Image:
    t = (t.clamp(-1, 1) + 1) / 2
    return Image.fromarray((t * 255).byte().cpu().permute(1, 2, 0).numpy(), "RGB")


# ─────────────────────────────────────────────────────────────────────────────

def encode_transaction(tx: Transaction, password: str,
                        cfg: Config, G: Generator,
                        salt: bytes | None = None) -> tuple[Image.Image, bytes]:
    """
    Embed the transaction compact token into a GAN-generated stego image.

    Returns (stego_image, salt). The salt must travel with the image.
    """
    G.eval()
    salt = salt or os.urandom(16)
    aes_key, prng_seed = _derive_keys(password, salt)

    blob = _aes_encrypt(encode_compact_token(tx), aes_key)   # 32 bytes
    m    = _bytes_to_tensor(blob, cfg.payload_bits, cfg.device).unsqueeze(0)

    gen = torch.Generator(); gen.manual_seed(prng_seed % 2**32)
    z   = torch.randn(1, cfg.noise_dim, generator=gen, device=cfg.device)

    with torch.no_grad():
        img = G(z, m).squeeze(0)
    return _tensor_to_pil(img), salt


def decode_transaction(stego_image: Image.Image, password: str,
                        salt: bytes, cfg: Config, E: Extractor) -> CompactToken:
    """Extract and decrypt the compact token from a stego image."""
    E.eval()
    aes_key, _ = _derive_keys(password, salt)
    img_t = _IMG_TRANSFORM(stego_image.convert("RGB")).unsqueeze(0).to(cfg.device)
    with torch.no_grad():
        bits = torch.sigmoid(E(img_t)).squeeze(0)
    blob = _tensor_to_bytes(bits)[:32]
    try:
        plain = _aes_decrypt(blob, aes_key)
    except Exception as e:
        raise ValueError(f"Stego decode failed: {e}")
    return decode_compact_token(plain[:16])


# ── image serialisation ──────────────────────────────────────────────────────

def image_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def b64_to_image(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
