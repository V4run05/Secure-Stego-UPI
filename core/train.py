"""
core/train.py
Joint G + D + E training loop.

Loss: L_total = alpha * L_adversarial + beta * L_reconstruction
    L_adversarial   = BCE(D(G(z,m)), 1)          — G fools D
    L_reconstruction = BCEWithLogits(E(G(z,m)), m) — E recovers m

Run from project root:
    python -c "from core.train import Trainer; from core.config import Config; Trainer(Config()).train()"
Or use run_training.py.
"""

import json
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision.utils import save_image

from core.config import Config
from core.models import Generator, Discriminator, Extractor, build_models
from core.dataset import get_dataloader
from core.crypto import NOISE_DIM


class Trainer:
    """
    Joint trainer for Generator, Discriminator, and Extractor.

    Args:
        cfg:        Config instance.
        dataloader: Optional custom DataLoader. If None, CelebA is used.

    Example:
        cfg = Config()
        cfg.num_epochs = 30
        Trainer(cfg).train()
    """

    def __init__(self, cfg: Config, dataloader: DataLoader | None = None) -> None:
        self.cfg    = cfg
        self.device = cfg.device

        self.G, self.D, self.E = build_models(cfg)

        self.opt_G = optim.Adam(self.G.parameters(), lr=cfg.lr_generator,     betas=(cfg.beta1, cfg.beta2))
        self.opt_D = optim.Adam(self.D.parameters(), lr=cfg.lr_discriminator, betas=(cfg.beta1, cfg.beta2))
        self.opt_E = optim.Adam(self.E.parameters(), lr=cfg.lr_extractor,     betas=(cfg.beta1, cfg.beta2))

        self.bce        = nn.BCELoss()
        self.bce_logits = nn.BCEWithLogitsLoss()

        self.dataloader = dataloader or get_dataloader(cfg)
        self.history: list[dict] = []

        Path(cfg.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(cfg.log_dir).mkdir(parents=True, exist_ok=True)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _rand_bits(self, b: int) -> torch.Tensor:
        """Random binary message tensor, shape (b, payload_bits)."""
        return torch.randint(0, 2, (b, self.cfg.payload_bits),
                             dtype=torch.float32, device=self.device)

    def _rand_noise(self, b: int) -> torch.Tensor:
        return torch.randn(b, NOISE_DIM, device=self.device)

    # ── training steps ───────────────────────────────────────────────────────

    def _step_D(self, real: torch.Tensor, fake: torch.Tensor) -> float:
        self.opt_D.zero_grad()
        b = real.size(0)
        loss = (
            self.bce(self.D(real), torch.ones(b,  device=self.device)) +
            self.bce(self.D(fake.detach()), torch.zeros(b, device=self.device))
        ) * 0.5
        loss.backward()
        self.opt_D.step()
        return loss.item()

    def _step_GE(self, z: torch.Tensor, m: torch.Tensor) -> tuple[float, float, float]:
        self.opt_G.zero_grad()
        self.opt_E.zero_grad()
        fake         = self.G(z, m)
        loss_adv     = self.bce(self.D(fake), torch.ones(z.size(0), device=self.device))
        loss_recon   = self.bce_logits(self.E(fake), m)
        loss_total   = self.cfg.alpha * loss_adv + self.cfg.beta * loss_recon
        loss_total.backward()
        self.opt_G.step()
        self.opt_E.step()
        return loss_adv.item(), loss_recon.item(), loss_total.item()

    # ── evaluation ───────────────────────────────────────────────────────────

    @torch.no_grad()
    def compute_ber(self, n_batches: int = 10) -> float:
        """Bit Error Rate: fraction of bits incorrectly recovered. Target < 0.05."""
        self.G.eval(); self.E.eval()
        total = wrong = 0
        for _ in range(n_batches):
            b    = self.cfg.batch_size
            z    = self._rand_noise(b)
            m    = self._rand_bits(b)
            m_hat = (torch.sigmoid(self.E(self.G(z, m))) >= 0.5).float()
            wrong += (m_hat != m).sum().item()
            total += m.numel()
        self.G.train(); self.E.train()
        return wrong / total

    # ── main loop ────────────────────────────────────────────────────────────

    def train(self) -> None:
        print(f"Device : {self.device}")
        print(f"Epochs : {self.cfg.num_epochs}  |  Batch : {self.cfg.batch_size}")
        print(f"Alpha  : {self.cfg.alpha}  |  Beta : {self.cfg.beta}")
        print(f"Batches/epoch: {len(self.dataloader)}")
        print("─" * 56)

        for epoch in range(1, self.cfg.num_epochs + 1):
            sum_D = sum_G = sum_R = 0.0

            for real_imgs, _ in self.dataloader:
                real_imgs = real_imgs.to(self.device)
                b = real_imgs.size(0)

                with torch.no_grad():
                    fake = self.G(self._rand_noise(b), self._rand_bits(b))

                sum_D += self._step_D(real_imgs, fake)
                sum_G_val, sum_R_val, _ = self._step_GE(self._rand_noise(b), self._rand_bits(b))
                sum_G += sum_G_val
                sum_R += sum_R_val

            n   = len(self.dataloader)
            ber = self.compute_ber()
            rec = {"epoch": epoch, "loss_D": round(sum_D/n, 4),
                   "loss_G": round(sum_G/n, 4), "loss_recon": round(sum_R/n, 4), "ber": round(ber, 4)}
            self.history.append(rec)

            print(f"[{epoch:3d}/{self.cfg.num_epochs}]  "
                  f"D={sum_D/n:.4f}  G={sum_G/n:.4f}  Recon={sum_R/n:.4f}  BER={ber:.4f}")

            if epoch % 5 == 0:
                self._save_samples(epoch)
                self._save_checkpoint(epoch)

        self._save_checkpoint("final")
        self._save_history()
        print("Training complete.")

    # ── persistence ──────────────────────────────────────────────────────────

    def _save_samples(self, tag) -> None:
        self.G.eval()
        with torch.no_grad():
            z = self._rand_noise(16)
            m = self._rand_bits(16)
            imgs = (self.G(z, m) + 1) / 2
            save_image(imgs, Path(self.cfg.log_dir) / f"samples_{tag}.png", nrow=4)
        self.G.train()

    def _save_checkpoint(self, tag) -> None:
        path = Path(self.cfg.checkpoint_dir) / f"checkpoint_{tag}.pt"
        torch.save({"G": self.G.state_dict(), "D": self.D.state_dict(), "E": self.E.state_dict()}, path)
        print(f"  Saved: {path}")

    def load_checkpoint(self, path: str) -> None:
        ck = torch.load(path, map_location=self.device)
        self.G.load_state_dict(ck["G"])
        self.D.load_state_dict(ck["D"])
        self.E.load_state_dict(ck["E"])
        print(f"Loaded: {path}")

    def _save_history(self) -> None:
        with open(Path(self.cfg.log_dir) / "history.json", "w") as f:
            json.dump(self.history, f, indent=2)
