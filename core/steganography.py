"""
core/steganography.py
Standalone text-message encode/decode via GAN steganography.
(The UPI layer uses upi/stego_bridge.py instead, which encodes binary payloads.)
"""

import io
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from core.config import Config
from core.models import Generator, Extractor
from core.crypto import (
    CryptoKeys, derive_keys, encrypt_message, decrypt_message,
    bytes_to_tensor, tensor_to_bytes, make_noise_vector, NOISE_DIM,
)


_to_tensor = transforms.Compose([
    transforms.Resize(64),
    transforms.CenterCrop(64),
    transforms.ToTensor(),
    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
])


def _tensor_to_pil(t: torch.Tensor) -> Image.Image:
    t = (t.clamp(-1, 1) + 1) / 2
    return Image.fromarray((t * 255).byte().cpu().permute(1, 2, 0).numpy(), "RGB")


def encode(message: str, password: str, cfg: Config, G: Generator,
           salt: bytes | None = None) -> tuple[Image.Image, bytes]:
    """
    Hide a text message inside a GAN-generated image.

    Returns: (stego_image, salt)  — store the salt; you need it to decode.
    """
    G.eval()
    keys, salt = derive_keys(password, salt=salt)
    m          = bytes_to_tensor(encrypt_message(message, keys), cfg.payload_bits).unsqueeze(0).to(cfg.device)
    z          = make_noise_vector(keys.prng_seed, device=cfg.device)
    with torch.no_grad():
        img = G(z, m).squeeze(0)
    return _tensor_to_pil(img), salt


def decode(stego_image: Image.Image, password: str, salt: bytes,
           cfg: Config, E: Extractor) -> str:
    """Recover a text message from a stego image."""
    E.eval()
    keys, _ = derive_keys(password, salt=salt)
    img_t   = _to_tensor(stego_image.convert("RGB")).unsqueeze(0).to(cfg.device)
    with torch.no_grad():
        bits = torch.sigmoid(E(img_t)).squeeze(0)
    return decrypt_message(tensor_to_bytes(bits), keys)


# ── image I/O helpers ────────────────────────────────────────────────────────

def image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO(); img.save(buf, format=fmt); return buf.getvalue()

def bytes_to_image(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw))

def save_image_file(img: Image.Image, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True); img.save(path)

def load_image_file(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")
