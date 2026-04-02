"""
core/config.py
All hyperparameters in one place. Import Config wherever you need settings.
Run from project root: securestego_upi/
"""

from dataclasses import dataclass
import torch


@dataclass
class Config:
    # Image
    image_size:     int = 64
    image_channels: int = 3

    # Payload: IV(16) + Ciphertext(16) = 32 bytes = 256 bits
    payload_bits: int = 256

    # GAN architecture
    noise_dim:    int = 100
    gen_features: int = 64
    dis_features: int = 64
    ext_features: int = 64

    # Training
    batch_size:       int   = 64
    num_epochs:       int   = 50
    lr_generator:     float = 2e-4
    lr_discriminator: float = 2e-4
    lr_extractor:     float = 1e-4
    beta1:            float = 0.5
    beta2:            float = 0.999
    alpha:            float = 1.0   # weight for adversarial loss
    beta:             float = 10.0  # weight for reconstruction loss

    # UPI-specific
    max_amount_rupees:   float = 42_949_672.95
    pin_challenge_count: int   = 3
    max_auth_attempts:   int   = 3
    session_ttl_seconds: int   = 300

    # Paths (relative to project root)
    dataset_path:   str = "data/celeba"
    checkpoint_dir: str = "checkpoints"
    log_dir:        str = "logs"
    db_path:        str = "securestego.db"

    @property
    def device(self) -> torch.device:
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
