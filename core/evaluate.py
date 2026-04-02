"""
core/evaluate.py
Phase 5 evaluation suite.

Run:
    python core/evaluate.py --checkpoint checkpoints/checkpoint_final.pt \
                            --real-dir data/celeba/celeba/img_align_celeba \
                            --output-dir eval_results
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")   # non-interactive backend — works without a display
import matplotlib.pyplot as plt
from PIL import Image
from torchvision import transforms

from core.config import Config
from core.models import build_models, Generator, Extractor
from core.crypto import NOISE_DIM


# ─────────────────────────────────────────────────────────────────────────────
#  BER vs capacity
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def compute_ber_vs_capacity(
    G: Generator, E: Extractor, cfg: Config,
    payload_sizes: list[int] | None = None,
    num_samples: int = 512,
) -> dict[int, float]:
    """Measure BER at different payload sizes (up to cfg.payload_bits)."""
    if payload_sizes is None:
        payload_sizes = [32, 64, 96, 128, 160, 192, 256]
    G.eval(); E.eval()
    d = cfg.device
    results = {}
    for bits in payload_sizes:
        if bits > cfg.payload_bits:
            results[bits] = None; continue
        total = wrong = 0
        while total < num_samples:
            b = min(cfg.batch_size, num_samples - total)
            z = torch.randn(b, NOISE_DIM, device=d)
            m = torch.randint(0, 2, (b, bits), dtype=torch.float32, device=d)
            m_pad = torch.zeros(b, cfg.payload_bits, device=d)
            m_pad[:, :bits] = m
            m_hat = (torch.sigmoid(E(G(z, m_pad)))[:, :bits] >= 0.5).float()
            wrong += (m_hat != m).sum().item()
            total += b
        results[bits] = round(wrong / (total * bits), 4)
        print(f"  {bits:3d} bits → BER: {results[bits]:.4f}")
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Generate samples for FID
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def generate_samples_for_fid(G: Generator, cfg: Config,
                              output_dir: str, num_samples: int = 1000) -> None:
    G.eval()
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    to_pil = transforms.ToPILImage()
    idx = 0
    while idx < num_samples:
        b = min(cfg.batch_size, num_samples - idx)
        z = torch.randn(b, NOISE_DIM, device=cfg.device)
        m = torch.randint(0, 2, (b, cfg.payload_bits), dtype=torch.float32, device=cfg.device)
        for img_t in ((G(z, m).clamp(-1, 1) + 1) / 2):
            to_pil(img_t.cpu()).save(out / f"sample_{idx:05d}.png")
            idx += 1
    print(f"Generated {num_samples} samples → {output_dir}")


# ─────────────────────────────────────────────────────────────────────────────
#  FID score
# ─────────────────────────────────────────────────────────────────────────────

def compute_fid_score(real_dir: str, fake_dir: str) -> float:
    """
    Compute FID. Requires: pip install pytorch-fid
    Returns -1.0 if pytorch-fid is not installed.
    """
    try:
        from pytorch_fid import fid_score
        return round(fid_score.calculate_fid_given_paths(
            [real_dir, fake_dir], batch_size=50,
            device="cuda" if torch.cuda.is_available() else "cpu", dims=2048,
        ), 2)
    except ImportError:
        print("Install pytorch-fid:  pip install pytorch-fid")
        return -1.0


# ─────────────────────────────────────────────────────────────────────────────
#  Pixel histogram (steganalysis)
# ─────────────────────────────────────────────────────────────────────────────

def plot_pixel_histogram(real_images: list[Image.Image],
                         stego_images: list[Image.Image],
                         save_path: str | None = None) -> None:
    def _vals(imgs):
        return np.array([v for img in imgs for v in np.array(img.convert("RGB")).flatten()])

    rv, sv = _vals(real_images), _vals(stego_images)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].hist(rv, bins=256, range=(0,255), alpha=0.6, color="steelblue", label="Real", density=True)
    axes[0].hist(sv, bins=256, range=(0,255), alpha=0.6, color="coral",     label="Stego", density=True)
    axes[0].set_title("Pixel value distribution"); axes[0].legend()

    axes[1].hist(rv % 4, bins=4, range=(0,4), alpha=0.7, color="steelblue", label="Real", density=True, rwidth=0.8)
    axes[1].hist(sv % 4, bins=4, range=(0,4), alpha=0.7, color="coral",     label="Stego", density=True, rwidth=0.8)
    axes[1].set_title("LSB analysis (2 least-significant bits)"); axes[1].legend()
    axes[1].set_xticks([0.5,1.5,2.5,3.5]); axes[1].set_xticklabels(["0","1","2","3"])

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Histogram saved: {save_path}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
#  LSB baseline (for comparison)
# ─────────────────────────────────────────────────────────────────────────────

def lsb_encode(image: Image.Image, message_bits: list[int]) -> Image.Image:
    """Classic LSB steganography. StegExpose should flag these; GAN images should pass."""
    pixels = list(image.getdata())
    flat   = [c for p in pixels for c in (p if isinstance(p, tuple) else [p])]
    for i, bit in enumerate(message_bits[:len(flat)]):
        flat[i] = (flat[i] & ~1) | bit
    channels = len(image.getbands())
    out = Image.new(image.mode, image.size)
    out.putdata([tuple(flat[i*channels:(i+1)*channels]) for i in range(image.width * image.height)])
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Full evaluation run
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation(checkpoint_path: str, real_image_dir: str,
                   output_dir: str = "eval_results") -> None:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    cfg = Config()

    G, _, E = build_models(cfg)
    ck = torch.load(checkpoint_path, map_location=cfg.device)
    G.load_state_dict(ck["G"]); E.load_state_dict(ck["E"])

    print("\n=== Generating stego samples ===")
    sample_dir = str(out / "stego_samples")
    generate_samples_for_fid(G, cfg, sample_dir, num_samples=200)

    print("\n=== BER vs Capacity ===")
    ber_results = compute_ber_vs_capacity(G, E, cfg)
    with open(out / "ber_vs_capacity.json", "w") as f:
        json.dump(ber_results, f, indent=2)

    print("\n=== Pixel Histogram ===")
    real_imgs  = [Image.open(p) for p in sorted(Path(real_image_dir).glob("*.jpg"))[:100]]
    stego_imgs = [Image.open(p) for p in sorted(Path(sample_dir).glob("*.png"))[:100]]
    if real_imgs and stego_imgs:
        plot_pixel_histogram(real_imgs, stego_imgs, save_path=str(out / "histogram.png"))
    else:
        print("  Skipped (no real images found)")

    print(f"\nDone. Results in: {output_dir}")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--real-dir",   required=True)
    ap.add_argument("--output-dir", default="eval_results")
    args = ap.parse_args()
    run_evaluation(args.checkpoint, args.real_dir, args.output_dir)
