"""
core/models.py
PyTorch architectures for the three GAN networks.
All imports use the package path (from core.xxx) so this works
when run from the project root: securestego_upi/
"""

import torch
import torch.nn as nn

from core.config import Config


def _weights_init(m: nn.Module) -> None:
    """DCGAN-standard weight initialisation for Conv and BatchNorm layers."""
    name = type(m).__name__
    if "Conv" in name:
        nn.init.normal_(m.weight.data, 0.0, 0.02)
    elif "BatchNorm" in name:
        nn.init.normal_(m.weight.data, 1.0, 0.02)
        nn.init.constant_(m.bias.data, 0)


# ─────────────────────────────────────────────────────────────────────────────
#  Generator G
# ─────────────────────────────────────────────────────────────────────────────

class Generator(nn.Module):
    """
    Encoder-Generator.
    Input:  z (noise, shape B×noise_dim) + m (message bits, shape B×payload_bits)
    Output: synthetic face image, shape B×3×64×64, values in [-1, 1]
    """
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        latent = cfg.noise_dim + cfg.payload_bits
        nf     = cfg.gen_features
        self.net = nn.Sequential(
            # 1×1 → 4×4
            nn.ConvTranspose2d(latent, nf * 8, 4, 1, 0, bias=False),
            nn.BatchNorm2d(nf * 8), nn.ReLU(True),
            # 4×4 → 8×8
            nn.ConvTranspose2d(nf * 8, nf * 4, 4, 2, 1, bias=False),
            nn.BatchNorm2d(nf * 4), nn.ReLU(True),
            # 8×8 → 16×16
            nn.ConvTranspose2d(nf * 4, nf * 2, 4, 2, 1, bias=False),
            nn.BatchNorm2d(nf * 2), nn.ReLU(True),
            # 16×16 → 32×32
            nn.ConvTranspose2d(nf * 2, nf, 4, 2, 1, bias=False),
            nn.BatchNorm2d(nf), nn.ReLU(True),
            # 32×32 → 64×64  (no BatchNorm on output layer)
            nn.ConvTranspose2d(nf, cfg.image_channels, 4, 2, 1, bias=False),
            nn.Tanh(),
        )
        self.apply(_weights_init)

    def forward(self, z: torch.Tensor, m: torch.Tensor) -> torch.Tensor:
        latent = torch.cat([z, m], dim=1).unsqueeze(-1).unsqueeze(-1)
        return self.net(latent)


# ─────────────────────────────────────────────────────────────────────────────
#  Discriminator D
# ─────────────────────────────────────────────────────────────────────────────

class Discriminator(nn.Module):
    """
    Binary classifier: real (CelebA) vs fake (generated).
    Input:  image B×3×64×64
    Output: scalar probability B (1=real, 0=fake)
    """
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        nf = cfg.dis_features
        self.net = nn.Sequential(
            # No BatchNorm on first layer (DCGAN rule)
            nn.Conv2d(cfg.image_channels, nf, 4, 2, 1, bias=False),
            nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf,      nf * 2, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 2), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf * 2,  nf * 4, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 4), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf * 4,  nf * 8, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 8), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf * 8,  1,      4, 1, 0, bias=False),
            nn.Sigmoid(),
        )
        self.apply(_weights_init)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).view(-1)


# ─────────────────────────────────────────────────────────────────────────────
#  Extractor E
# ─────────────────────────────────────────────────────────────────────────────

class Extractor(nn.Module):
    """
    Decoder: recovers message bits from a stego image.
    Input:  stego image B×3×64×64
    Output: logits B×payload_bits  (apply sigmoid + threshold ≥0.5 to get bits)
    """
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        nf = cfg.ext_features
        self.conv = nn.Sequential(
            nn.Conv2d(cfg.image_channels, nf,     4, 2, 1, bias=False), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf,     nf * 2, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 2), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf * 2, nf * 4, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 4), nn.LeakyReLU(0.2, True),
            nn.Conv2d(nf * 4, nf * 8, 4, 2, 1, bias=False), nn.BatchNorm2d(nf * 8), nn.LeakyReLU(0.2, True),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(nf * 8 * 4 * 4, 512), nn.ReLU(True), nn.Dropout(0.3),
            nn.Linear(512, cfg.payload_bits),
        )
        self.apply(_weights_init)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.conv(x))


# ─────────────────────────────────────────────────────────────────────────────
#  Factory
# ─────────────────────────────────────────────────────────────────────────────

def build_models(cfg: Config) -> tuple[Generator, Discriminator, Extractor]:
    """
    Build and move all three networks to cfg.device.

    Usage:
        cfg = Config()
        G, D, E = build_models(cfg)
    """
    d = cfg.device
    return Generator(cfg).to(d), Discriminator(cfg).to(d), Extractor(cfg).to(d)
