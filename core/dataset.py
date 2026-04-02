"""
core/dataset.py
CelebA dataloader. Images are resized to 64×64 and normalised to [-1, 1].

get_dataloader() automatically detects whether you have images already on
disk and avoids the CelebA Google Drive downloader entirely in that case.

Expected layout after manual download:
    data/celeba/celeba/img_align_celeba/
        000001.jpg
        000002.jpg
        ...
"""

from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from torchvision import datasets, transforms
from torchvision.transforms import InterpolationMode
from PIL import Image

from core.config import Config


def _transform(image_size: int) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize(image_size, interpolation=InterpolationMode.BILINEAR),
        transforms.CenterCrop(image_size),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),  # → [-1, 1]
    ])


# ── flat-folder dataset ───────────────────────────────────────────────────────

class FlatImageDataset(Dataset):
    """
    Loads every .jpg / .jpeg / .png directly from a folder with no subdirectories.
    This is what you need for img_align_celeba/ which has no class subfolders.
    Returns (image_tensor, 0) so the training loop works identically to CelebA.
    """
    EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, folder: str, transform) -> None:
        folder = Path(folder)
        if not folder.exists():
            raise FileNotFoundError(f"Image folder not found: {folder}")
        self.paths     = sorted(
            p for p in folder.iterdir()
            if p.suffix.lower() in self.EXTENSIONS
        )
        if not self.paths:
            raise RuntimeError(
                f"No images found in {folder}. "
                "Expected .jpg / .png files directly inside the folder."
            )
        self.transform = transform

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int):
        img = Image.open(self.paths[idx]).convert("RGB")
        return self.transform(img), 0


# ── candidate paths to check for existing images ─────────────────────────────

def _find_existing_images(cfg: Config) -> Path | None:
    """
    Check the standard locations where CelebA images might already exist.
    Returns the first folder found that contains at least one image, else None.
    """
    root = Path(cfg.dataset_path)
    candidates = [
        root / "celeba" / "img_align_celeba",   # torchvision standard layout
        root / "img_align_celeba",               # one level up if user extracted here
        root,                                    # images dumped directly in dataset_path
    ]
    for candidate in candidates:
        if candidate.is_dir():
            imgs = [p for p in candidate.iterdir()
                    if p.suffix.lower() in FlatImageDataset.EXTENSIONS]
            if imgs:
                return candidate
    return None


# ── public loaders ────────────────────────────────────────────────────────────

def get_dataloader(cfg: Config) -> DataLoader:
    """
    Return a DataLoader for face images.

    Priority:
      1. If img_align_celeba/ (or similar) already exists on disk → use it
         directly via FlatImageDataset, skipping all download logic.
      2. Otherwise attempt torchvision's CelebA auto-download (often rate-limited).

    If auto-download also fails, run with --data-dir pointing at your images:
        python run_training.py --data-dir data/celeba/celeba/img_align_celeba
    """
    existing = _find_existing_images(cfg)
    if existing is not None:
        print(f"Found existing images at: {existing}")
        dataset = FlatImageDataset(str(existing), _transform(cfg.image_size))
        print(f"Loaded {len(dataset):,} images.")
        return _make_loader(dataset, cfg)

    # Fall back to torchvision downloader
    print("No local images found — attempting CelebA auto-download...")
    root = Path(cfg.dataset_path)
    root.mkdir(parents=True, exist_ok=True)
    try:
        dataset = datasets.CelebA(
            root=str(root), split="train",
            transform=_transform(cfg.image_size), download=True,
        )
        return _make_loader(dataset, cfg)
    except Exception as e:
        raise RuntimeError(
            f"CelebA download failed: {e}\n\n"
            "Fix: point --data-dir at your image folder, e.g.:\n"
            "  python run_training.py --data-dir data/celeba/celeba/img_align_celeba"
        ) from e


def get_folder_dataloader(folder_path: str, cfg: Config) -> DataLoader:
    """
    Load images from any flat folder of .jpg/.png files.
    No subdirectories required — images can be directly inside folder_path.
    """
    dataset = FlatImageDataset(folder_path, _transform(cfg.image_size))
    return _make_loader(dataset, cfg)


def _make_loader(dataset, cfg: Config) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size  = cfg.batch_size,
        shuffle     = True,
        num_workers  = 0,          # 0 = main process only; safe on Windows
        pin_memory  = cfg.device.type == "cuda",
        drop_last   = True,
    )
