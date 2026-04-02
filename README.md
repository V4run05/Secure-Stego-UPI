# SecureStego-UPI

**Coverless GAN Steganography as a Tamper-Evident Transaction Channel for UPI Authentication**

> A novel multi-factor UPI authentication system where a Generative Adversarial Network synthesises a carrier image directly from encrypted transaction data — no cover image, no modification, no trace.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Academic Context](#academic-context)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Verify the Backend](#verify-the-backend)
  - [Running the Backend Server](#running-the-backend-server)
- [Frontend Integration Guide](#frontend-integration-guide)
  - [Project Structure for Frontend](#project-structure-for-frontend)
  - [API Reference](#api-reference)
  - [Complete Frontend Workflow](#complete-frontend-workflow)
  - [Example Flask Wiring](#example-flask-wiring)
- [Training the Model](#training-the-model)
- [Evaluating the Model](#evaluating-the-model)
- [Module Reference](#module-reference)
- [Security Design](#security-design)
- [Known Limitations](#known-limitations)
- [Team](#team)

---

## Overview

Current UPI authentication relies on a static PIN as the final barrier before a transaction is authorised. Once a device is stolen or a PIN is shoulder-surfed, there is no further protection.

SecureStego-UPI addresses this with a three-layer authentication system built around a cryptographic novelty: **the transaction confirmation image itself is the authentication token**. A GAN generates a synthetic face image that visually conceals an AES-encrypted transaction payload. The image carries the amount, recipient, and a one-time session token. The PIN challenge positions for that transaction are derived from the hidden session token — meaning an attacker who intercepts the image cannot predict which digits will be asked for, cannot replay a previous transaction, and cannot tamper with the amount or recipient without breaking the hidden payload.

---

## How It Works

```
User initiates a payment
        │
        ▼
[Layer 1] Face authentication
  ArcFace biometric verification + liveness detection
  Rejects photos, videos, and spoofing attempts
        │
        ▼  (face verified)
GAN Encoder
  Encrypts {tx_id, amount, recipient, session_token} with AES-128-CBC
  Feeds the ciphertext bits into the Generator as part of the latent vector
  Outputs a synthetic face image that looks natural but carries hidden data
        │
        ▼
Stego image transmitted to user's device
  User app decodes it to confirm: correct amount? correct recipient?
  If the image was tampered with in transit, the hidden MAC fails
        │
        ▼
[Layer 2] Dynamic PIN challenge
  Challenge positions = HMAC(session_token, tx_id)
  session_token is hidden inside the stego image
  Only the legitimate user who decoded the image knows which positions are challenged
  User enters only the 3 challenged digits — observer cannot reconstruct full PIN
        │
        ▼  (PIN verified)
Transaction authorised
```

**Why coverless steganography matters here:**
Traditional steganography embeds data into an existing cover image by modifying pixel values. This leaves statistical traces that automated steganalysis tools (StegExpose, CNN-based detectors) can detect. More critically, if the original unmodified image is found online, a bitwise subtraction immediately reveals the payload. A GAN-generated image has no original — it was never a real photograph. There is nothing to compare it against.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Authentication Flow                   │
│                                                         │
│  Password ──► PBKDF2-HMAC-SHA256 ──► AES-128 key        │
│                                  └──► PRNG seed         │
│                                                         │
│  Message ──► AES-128-CBC ──► 256-bit tensor (m)         │
│  PRNG seed ──► Noise vector (z)                         │
│                                                         │
│  Generator G: [z ∥ m] ──► Stego image I_stego          │
│  Extractor E: I_stego ──► m̂ ──► AES decrypt ──► Message │
│  Discriminator D: (training only) real vs fake          │
│                                                         │
│  Loss = α · L_adversarial + β · L_reconstruction        │
└─────────────────────────────────────────────────────────┘
```

**GAN architecture (DCGAN):**

- Generator: transposed convolutions, 1×1 → 4×4 → 8×8 → 16×16 → 32×32 → 64×64
- Discriminator: strided convolutions, outputs raw logits (no Sigmoid)
- Extractor: mirror of Discriminator + FC head → 256-bit logits
- Training: two-phase — Phase 1 trains G+E on reconstruction only; Phase 2 introduces D

**Cryptographic chain:**

- Key derivation: PBKDF2-HMAC-SHA256, 200,000 iterations, 16-byte random salt
- Encryption: AES-128-CBC with random IV prepended to ciphertext
- PIN hashing: bcrypt (cost 12)
- PIN challenge: HMAC-SHA256(session_token, tx_id) → deterministic position selection
- PIN verification: two-layer HMAC chain — no plaintext PIN ever stored or transmitted after registration

---

## Repository Structure

```
SecureStego-UPI/
│
├── core/                        # GAN backbone — training and inference
│   ├── config.py                # All hyperparameters in one place
│   ├── crypto.py                # AES-128, PBKDF2, bit tensor conversion, seeded noise
│   ├── dataset.py               # CelebA DataLoader (auto-detects local images)
│   ├── models.py                # Generator, Discriminator, Extractor (PyTorch)
│   ├── steganography.py         # Standalone text-message encode/decode
│   ├── train.py                 # Joint G+D+E training loop
│   ├── evaluate.py              # Phase 5: BER curves, FID score, histogram, LSB baseline
│   └── __init__.py
│
├── upi/                         # UPI application layer
│   ├── auth_pipeline.py         # Full 3-layer orchestrator (register / initiate / verify)
│   ├── database.py              # SQLite persistence (users, transactions, PIN sessions)
│   ├── dynamic_pin.py           # HMAC-based dynamic PIN challenge and verification
│   ├── face_auth.py             # ArcFace/FaceNet + LBP liveness detection
│   ├── stego_bridge.py          # Connects GAN encoder/decoder to transaction layer
│   ├── transaction.py           # Compact 16-byte transaction token encoding
│   └── __init__.py
│
├── frontend/                    # Frontend lives here (see Frontend Integration Guide)
│   └── .gitkeep
│
├── checkpoints/
│   └── checkpoint_final.pt      # Trained model weights (60 MB)
│
├── api.py                       # PUBLIC API — the only file the frontend needs
├── run_training.py              # Local training launcher (CLI)
├── verify_backend.py            # End-to-end backend verification (22 checks)
├── kaggle_train.py              # Self-contained Kaggle notebook training script
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Academic Context

**Course:** Cryptography and Network Security — Design Assignment 1

**Core contribution:** Prior work on coverless steganography (Volkhonskiy et al. 2017; Hu et al. 2018) does not address the Extractor Ambiguity Problem: when the Generator takes a random noise vector z alongside message m, the Extractor at the receiver cannot separate the contribution of m from z because z varies randomly per generation. This project solves it by making z deterministic through key derivation — both sender and receiver independently compute the same z from the shared password, so the Extractor only needs to invert the message-conditioned component.

**References:**

1. Volkhonskiy, D., Nazarov, I., & Burnaev, E. (2017). _Steganographic Generative Adversarial Networks._ VISAPP.
2. Fridrich, J., & Kodovsky, J. (2012). _Rich Models for Steganalysis of Digital Images._ IEEE T-IFS.
3. Hu, D., Wang, L., Jiang, W., & Zheng, S. (2018). _A Novel Image Steganography Method via Deep Convolutional Generative Adversarial Networks._ IEEE Access.
4. Jain, A. K., Ross, A., & Prabhakar, S. (2004). _An Introduction to Biometric Recognition._ IEEE T-CSVT.

**Training results:**
| Metric | Value |
|--------|-------|
| Final BER | 0.0008 |
| Sanity BER (16 samples) | 0.0002 |
| Training time | 89 min on Tesla T4 |
| Dataset | CelebA — 162,770 images (official train split) |

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip
- Git
- A trained checkpoint at `checkpoints/checkpoint_final.pt` (already in the repo)

Face authentication requires DeepFace. Without it, the system runs in **mock mode** — face auth always passes. Mock mode is fine for development and all 22 backend tests pass either way.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/V4run05/Secure-Stego-UPI.git
cd SecureStego-UPI

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Face authentication — skip for development
pip install deepface
```

### Verify the Backend

Run this before anything else. It executes 22 checks covering every module — crypto, database, PIN logic, models, and the full API flow — using random weights and in-memory state. No GPU, no dataset, no trained checkpoint required.

```bash
python verify_backend.py
```

Expected output:

```
SecureStego-UPI — Backend Verification
──────────────────────────────────────────────
  [ PASS ] Imports
  [ PASS ] Config
  [ PASS ] Model construction
  [ PASS ] Forward pass (G, D, E)
  [ PASS ] Crypto — AES round-trip
  [ PASS ] Crypto — key derivation (deterministic)
  [ PASS ] Crypto — bit tensor conversion
  [ PASS ] Database — user CRUD
  [ PASS ] Database — face embedding store/load
  [ PASS ] Database — registration MACs store/load
  [ PASS ] Database — transaction save/load
  [ PASS ] Database — PIN session save/load/delete
  [ PASS ] Transaction — compact token encode/decode
  [ PASS ] Transaction — tamper detection
  [ PASS ] Dynamic PIN — hash + challenge
  [ PASS ] Dynamic PIN — correct digits pass
  [ PASS ] Dynamic PIN — wrong digits fail
  [ PASS ] API — register_user()
  [ PASS ] API — initiate_transaction()
  [ PASS ] API — verify_transaction() correct PIN
  [ PASS ] API — verify_transaction() wrong PIN
  [ PASS ] API — health()
──────────────────────────────────────────────
  All 22 checks passed. Backend is ready.
```

If any check fails, run with `--verbose` for full tracebacks:

```bash
python verify_backend.py --verbose
```

### Running the Backend Server

Install Flask (or FastAPI, your choice), then wire up four endpoints:

```bash
pip install flask
```

```python
# server.py — minimal example
from flask import Flask, request, jsonify
from api import SecureStegoUPI
import os

app = Flask(__name__)

api = SecureStegoUPI.from_checkpoint(
    checkpoint_path = "checkpoints/checkpoint_final.pt",
    app_secret      = os.environ.get("APP_SECRET", "change-this-before-deployment"),
)

@app.post("/auth/register")
def register():
    b = request.json
    return jsonify(api.register_user(b["user_id"], b["face_image_b64"], b["pin"]))

@app.post("/transaction/initiate")
def initiate():
    b = request.json
    return jsonify(api.initiate_transaction(
        b["user_id"], b["face_image_b64"], b["amount_rupees"], b["recipient_upi"]
    ))

@app.post("/transaction/verify")
def verify():
    b = request.json
    return jsonify(api.verify_transaction(b["tx_id"], b["pin_digits"]))

@app.get("/health")
def health():
    return jsonify(api.health())

if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

```bash
python server.py
```

---

## Frontend Integration Guide

> **This section is specifically for the frontend developer.**

### Project Structure for Frontend

Create your frontend inside the `frontend/` folder at the repo root. The backend and frontend are completely independent — you never need to touch anything outside `frontend/` except for calling the four API endpoints.

```
SecureStego-UPI/
├── backend files (core/, upi/, api.py, etc.)  ← do not modify
└── frontend/
    └── your project here (React, Next.js, plain HTML — anything)
```

### First-time setup

```bash
git clone https://github.com/V4ru05/Secure-Stego-UPI.git
cd SecureStego-UPI

# Set up the backend
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
pip install -r requirements.txt
python verify_backend.py        # confirm all 22 checks pass

# Start the backend server
python server.py                # runs on http://localhost:5000
```

You do not need to install PyTorch, train anything, or understand any backend code. The checkpoint is already in the repo. As long as `python server.py` starts without errors, the backend is running.

### API Reference

All requests are JSON. All responses are JSON. The backend runs at `http://localhost:5000` by default.

---

#### `POST /auth/register`

Register a new user with their face and PIN. Call this once when a user signs up.

**Request:**

```json
{
  "user_id": "varun@okicici",
  "face_image_b64": "<base64-encoded PNG of the user's face>",
  "pin": "482931"
}
```

**Response (success):**

```json
{
  "success": true,
  "user_id": "varun@okicici",
  "reason": "Registration successful"
}
```

**Response (failure):**

```json
{
  "success": false,
  "user_id": "varun@okicici",
  "reason": "User already registered: varun@okicici"
}
```

**Notes:**

- `face_image_b64` must be a base64-encoded PNG or JPEG. Capture it from the device camera using the Web Camera API or a file upload.
- `pin` must be a string of 4–6 digits.
- In mock mode (DeepFace not installed), any face image is accepted.

---

#### `POST /transaction/initiate`

Start a transaction. This runs face authentication and returns the stego image plus the PIN challenge.

**Request:**

```json
{
  "user_id": "varun@okicici",
  "face_image_b64": "<base64 live camera capture>",
  "amount_rupees": 500.0,
  "recipient_upi": "kailash@okaxis"
}
```

**Response (success):**

```json
{
  "tx_id": "3f2a1b4c-...",
  "stego_image_b64": "<base64 PNG — display this to the user>",
  "salt_b64": "<base64 bytes — store this, send it back on /verify>",
  "pin_positions": [1, 3, 5],
  "amount_rupees": 500.0,
  "recipient_upi": "kailash@okaxis"
}
```

**Response (face auth failed):**

```json
{
  "error": "Face authentication failed: liveness check failed",
  "attempts_remaining": 2
}
```

**Notes:**

- Store `tx_id` and `salt_b64` in component state — you need both for the verify call.
- Display `stego_image_b64` as an `<img src="data:image/png;base64,{stego_image_b64}">`. It looks like a generated face photo.
- Display `pin_positions` to the user as a prompt: _"Enter digits at positions 1, 3, and 5 of your PIN."_
- Display `amount_rupees` and `recipient_upi` as a confirmation screen so the user can verify before entering their PIN.

---

#### `POST /transaction/verify`

Submit the user's PIN response to authorise the transaction.

**Request:**

```json
{
  "tx_id": "3f2a1b4c-...",
  "pin_digits": {
    "1": "4",
    "3": "8",
    "5": "3"
  }
}
```

`pin_digits` keys are the positions from `pin_positions` in the initiate response (as strings). Values are the single digit the user entered for that position.

**Response (authorised):**

```json
{
  "authorized": true,
  "receipt": {
    "tx_id": "3f2a1b4c-...",
    "sender_upi": "varun@okicici",
    "recipient_upi": "kailash@okaxis",
    "amount_rupees": 500.0,
    "timestamp": 1775124854,
    "status": "authorized"
  },
  "reason": "Transaction authorized successfully",
  "attempts_remaining": 3
}
```

**Response (wrong PIN):**

```json
{
  "authorized": false,
  "receipt": null,
  "reason": "Incorrect PIN digit(s)",
  "attempts_remaining": 2
}
```

**Notes:**

- If `authorized` is false and `attempts_remaining` reaches 0, the account is locked for 5 minutes.
- On success, use `receipt` to display a transaction confirmation screen.
- The `tx_id` is single-use — once verified (or rejected after max attempts), it cannot be reused.

---

#### `GET /health`

Check if the backend is running. Use this to show a connection status indicator.

**Response:**

```json
{
  "status": "ok",
  "device": "cuda",
  "payload_bits": 256,
  "image_size": 64,
  "cuda_available": true,
  "timestamp": 1775124854
}
```

---

### Complete Frontend Workflow

Here is the end-to-end flow to implement across your screens:

```
Screen 1 — Registration
  ├── Capture face photo (camera)
  ├── User enters PIN (4-6 digits)
  └── POST /auth/register
      ├── success → navigate to home
      └── failure → show error message

Screen 2 — Initiate payment
  ├── User enters: recipient UPI ID, amount
  ├── Capture live face photo (camera)
  └── POST /transaction/initiate
      ├── error (face failed) → show error + attempts remaining
      └── success →

Screen 3 — Transaction confirmation
  ├── Show stego image (img src=data:image/png;base64,...)
  ├── Show: "Paying ₹{amount} to {recipient}"
  ├── Show: "Enter digits {positions} of your PIN"
  ├── Input fields for each challenged position
  └── POST /transaction/verify
      ├── authorized: true  → Screen 4 (success)
      └── authorized: false → show error, remaining attempts, allow retry

Screen 4 — Success
  └── Show receipt (tx_id, amount, recipient, timestamp)
```

### Example Flask Wiring

See [Running the Backend Server](#running-the-backend-server) above. For **FastAPI**, the pattern is identical — replace `request.json` with Pydantic models and `jsonify` with `return`.

### Development tips

- **Before the checkpoint is set up:** use `SecureStegoUPI.untrained()` instead of `from_checkpoint()`. All API responses have the correct shape; stego images will look like noise but every other field is real.
- **CORS:** if your frontend runs on a different port (e.g. React on 3000, Flask on 5000), install `flask-cors` and add `CORS(app)` to the server.
- **Face image capture:** use `navigator.mediaDevices.getUserMedia` in the browser and draw a frame to a `<canvas>`, then call `canvas.toDataURL('image/png')` and strip the `data:image/png;base64,` prefix before sending.
- **PIN input UI:** render one input box per challenged position (e.g. three boxes for positions 1, 3, 5). Do not show the position numbers in sequence — show them labelled: "Position 1", "Position 3", "Position 5". Single-character inputs with `maxLength={1}` and `type="tel"` work well on mobile.

---

## Training the Model

The trained checkpoint is already in the repo. **You do not need to retrain unless you want to experiment.**

### Local training (slow — for testing only)

```bash
# Quick smoke test — 5 epochs, confirms training works
python run_training.py --epochs 5

# Full training — very slow on CPU (hours per epoch)
python run_training.py --epochs 50

# With your own image folder instead of CelebA
python run_training.py --epochs 50 --data-dir path/to/face/images
```

### Kaggle training (recommended — ~90 min on Tesla T4)

1. Go to [kaggle.com](https://kaggle.com) → New Notebook
2. Settings → Accelerator → **GPU T4 x2** or **P100**
3. Add Data → search **"celeba"** → add **CelebFaces Attributes (CelebA) Dataset** by Jessica Li
4. Upload `kaggle_train.py` or paste its contents into a code cell
5. Run — checkpoint saves to `/kaggle/working/checkpoint_final.pt`
6. Download from the Output panel and replace `checkpoints/checkpoint_final.pt`

### What to watch during training

| Signal         | Healthy                       | Problem                                |
| -------------- | ----------------------------- | -------------------------------------- |
| Phase 1 Recon  | Drops from 0.693 toward ~0.25 | Stuck at 0.693 → increase `beta_recon` |
| Phase 1 BER    | Drops to < 0.05 by epoch 5–10 | Stuck at 0.50 → E is not learning      |
| Phase 2 D loss | Oscillates 0.05–0.35          | Near zero → D dominating G             |
| Phase 2 BER    | Holds or continues improving  | Rising above 0.10 → lower `alpha`      |

---

## Evaluating the Model

```bash
python core/evaluate.py \
    --checkpoint checkpoints/checkpoint_final.pt \
    --real-dir   data/celeba/celeba/img_align_celeba \
    --output-dir eval_results
```

Outputs:

- `eval_results/ber_vs_capacity.json` — BER at payload sizes 32 to 256 bits
- `eval_results/histogram.png` — pixel distribution: real vs stego (visual steganalysis)
- `eval_results/stego_samples/` — 200 generated stego images

For FID score:

```bash
pip install pytorch-fid
python -c "from core.evaluate import compute_fid_score; print(compute_fid_score('data/celeba/celeba/img_align_celeba', 'eval_results/stego_samples'))"
```

---

## Module Reference

| File                   | Purpose                                                                                                          |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `api.py`               | Public API — `SecureStegoUPI` class with `register_user`, `initiate_transaction`, `verify_transaction`, `health` |
| `core/config.py`       | All hyperparameters. Change values here to tune training.                                                        |
| `core/models.py`       | `Generator`, `Discriminator`, `Extractor` PyTorch classes. `build_models(cfg)` factory.                          |
| `core/crypto.py`       | `derive_keys`, `aes_encrypt`, `aes_decrypt`, `bytes_to_tensor`, `tensor_to_bytes`, `make_noise_vector`           |
| `core/train.py`        | `Trainer` class — instantiate with `Config`, call `.train()`                                                     |
| `core/evaluate.py`     | `compute_ber_vs_capacity`, `compute_fid_score`, `plot_pixel_histogram`, `lsb_encode`                             |
| `upi/transaction.py`   | `Transaction` dataclass, `encode_compact_token`, `decode_compact_token`, `verify_compact_token`                  |
| `upi/database.py`      | `DatabaseManager` — SQLite wrapper for users, embeddings, transactions, PIN sessions                             |
| `upi/face_auth.py`     | `register_face`, `verify_face`, `check_liveness` — wraps DeepFace with mock fallback                             |
| `upi/dynamic_pin.py`   | `hash_pin`, `build_registration_macs`, `generate_challenge`, `check_pin_response`                                |
| `upi/stego_bridge.py`  | `encode_transaction`, `decode_transaction` — bridges GAN and UPI transaction layer                               |
| `upi/auth_pipeline.py` | `AuthPipeline` — full orchestrator used internally by `api.py`                                                   |

---

## Security Design

**What is protected:**

- The secret message (transaction details) is AES-128-CBC encrypted before embedding. An attacker who recovers the stego image bits still has ciphertext.
- The UPI PIN is never stored in plaintext. At registration, per-position HMACs are derived using a server secret and stored instead. The plaintext PIN is discarded immediately after registration.
- Dynamic PIN challenge positions change every transaction — keyed to both the session token (hidden in the stego image) and the transaction ID. A recorded transaction's PIN response cannot be replayed.
- The session token is embedded in the stego image. An attacker who does not know the shared password cannot extract it, and therefore cannot predict which PIN positions will be challenged.

**What is not protected (known limitations — see below):**

- The server's `APP_SECRET` must be kept secret. If it leaks, registration MACs can be forged.
- The stego image quality at 64×64 resolution limits the visual realism achievable.

---

## Known Limitations

- **Image resolution:** The model generates 64×64 images. This is sufficient for steganalysis resistance evaluation but not realistic enough to be mistaken for a real photograph at full size. Increasing to 128×128 requires retraining with a larger architecture.
- **Mock face auth:** Without DeepFace installed, face authentication always passes. This is intentional for development but must not be used in any real deployment.
- **SQLite:** The database uses SQLite which is not suitable for concurrent multi-server deployments. Replace with PostgreSQL using the same `DatabaseManager` interface for production.
- **Session TTL:** Transaction sessions expire after 5 minutes (configurable in `Config`). Expired transactions cannot be completed and a new transaction must be initiated.
- **APP_SECRET:** The default fallback secret is `"change-this-before-deployment"`. Always set the `APP_SECRET` environment variable before running.

---

## Team

| Name             | Role                                            | RegNo     |
| ---------------- | ----------------------------------------------- | --------- |
| Varun R Panicker | GAN steganography, cryptographic layer, backend | 23BAI1350 |
| Kailash Murali T | UPI authentication design, frontend             | 23BAI1427 |

**Course:** Cryptography and Network Security — VIT Chennai

---

<div align="center">
  <sub>Built with PyTorch · AES-128 · PBKDF2 · bcrypt · SQLite · DeepFace</sub>
</div>
