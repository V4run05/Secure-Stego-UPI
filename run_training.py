"""
run_training.py
===============
Training launcher for SecureStego-UPI.

Run from the project root (securestego_upi/):

    python run_training.py                          # full training, CelebA
    python run_training.py --epochs 10              # quick smoke test
    python run_training.py --data-dir data/myfaces  # custom image folder
    python run_training.py --resume checkpoints/checkpoint_10.pt

Progress is printed every epoch. Checkpoints saved every 5 epochs and on
completion. Sample images saved to logs/samples_<epoch>.png.
"""

import argparse
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Train the SecureStego-UPI GAN")
    p.add_argument("--epochs",      type=int,   default=None,    help="Override num_epochs")
    p.add_argument("--batch-size",  type=int,   default=None,    help="Override batch_size")
    p.add_argument("--alpha",       type=float, default=None,    help="Adversarial loss weight")
    p.add_argument("--beta",        type=float, default=None,    help="Reconstruction loss weight")
    p.add_argument("--data-dir",    type=str,   default=None,    help="Custom image folder (uses ImageFolder loader)")
    p.add_argument("--resume",      type=str,   default=None,    help="Path to checkpoint to resume from")
    p.add_argument("--checkpoint-dir", type=str, default=None,   help="Where to save checkpoints")
    p.add_argument("--log-dir",     type=str,   default=None,    help="Where to save sample images")
    return p.parse_args()


def main():
    args = parse_args()

    from core.config import Config
    from core.train import Trainer

    cfg = Config()

    # Apply CLI overrides
    if args.epochs:       cfg.num_epochs      = args.epochs
    if args.batch_size:   cfg.batch_size      = args.batch_size
    if args.alpha:        cfg.alpha           = args.alpha
    if args.beta:         cfg.beta            = args.beta
    if args.checkpoint_dir: cfg.checkpoint_dir = args.checkpoint_dir
    if args.log_dir:      cfg.log_dir         = args.log_dir

    print("=" * 56)
    print("  SecureStego-UPI — GAN Training")
    print("=" * 56)
    print(f"  Device        : {cfg.device}")
    print(f"  Epochs        : {cfg.num_epochs}")
    print(f"  Batch size    : {cfg.batch_size}")
    print(f"  Payload bits  : {cfg.payload_bits}")
    print(f"  alpha / beta  : {cfg.alpha} / {cfg.beta}")
    print(f"  Checkpoints   : {cfg.checkpoint_dir}/")
    print(f"  Sample images : {cfg.log_dir}/")
    print("=" * 56)

    # Build dataloader
    dataloader = None
    if args.data_dir:
        print(f"\nUsing custom image folder: {args.data_dir}")
        if not Path(args.data_dir).exists():
            print(f"ERROR: --data-dir '{args.data_dir}' does not exist.")
            sys.exit(1)
        from core.dataset import get_folder_dataloader
        dataloader = get_folder_dataloader(args.data_dir, cfg)
        print(f"Loaded {len(dataloader.dataset):,} images.\n")
    else:
        # Auto-detect: check if images are already on disk before trying to download
        from core.dataset import _find_existing_images
        found = _find_existing_images(cfg)
        if found:
            print(f"\nAuto-detected images at: {found}")
            print("Skipping download — using local files.\n")
        else:
            print("\nNo local images found. Attempting CelebA auto-download.")
            print("If this fails, run with --data-dir:")
            print("  python run_training.py --data-dir data\\celeba\\celeba\\img_align_celeba\n")

    trainer = Trainer(cfg, dataloader=dataloader)

    if args.resume:
        print(f"Resuming from: {args.resume}")
        trainer.load_checkpoint(args.resume)

    trainer.train()

    print("\nDone. Final checkpoint: checkpoints/checkpoint_final.pt")
    print("Run verification:  python verify_backend.py")


if __name__ == "__main__":
    main()