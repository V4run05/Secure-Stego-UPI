# SecureStego-UPI

A novel multi-factor UPI payment authentication system that uses Coverless GAN Steganography to create tamper-evident transaction channels.

## Architecture

### Frontend (React + Vite)
- **Framework:** React 18 (TypeScript)
- **Build Tool:** Vite 6
- **Styling:** Tailwind CSS 4, Radix UI, Lucide React
- **Routing:** React Router 7
- **Animations:** Motion (Framer Motion)
- **Package Manager:** pnpm
- **Location:** `frontend/`
- **Dev Port:** 5000

### Backend (Python — AI/ML)
- **Framework:** Flask (API described in `api.py`)
- **Deep Learning:** PyTorch (DCGAN architecture)
- **Face Auth:** DeepFace (optional — runs in mock mode without it)
- **Cryptography:** pycryptodome (AES-128-CBC), bcrypt
- **Database:** SQLite (via `upi/database.py`)

## Project Structure

```
SecureStego-UPI/
├── core/                # GAN Backbone (Models & Training)
│   ├── models.py        # Generator, Discriminator, Extractor
│   ├── crypto.py        # Encryption & bit-to-tensor conversion
│   ├── train.py         # GAN training loops
│   └── evaluate.py      # BER, FID score metrics
├── upi/                 # UPI Application Layer
│   ├── auth_pipeline.py # Face auth + stego + PIN orchestration
│   ├── face_auth.py     # Biometric verification
│   ├── dynamic_pin.py   # HMAC-based challenge generation
│   └── database.py      # SQLite persistence
├── frontend/            # React/Vite Frontend
│   ├── src/app/         # UI components
│   └── vite.config.ts   # Vite config (port 5000, host 0.0.0.0)
├── checkpoints/         # Trained model weights
├── api.py               # Public API (SecureStegoUPI class)
├── requirements.txt     # Python dependencies
└── replit.md            # This file
```

## Authentication Flow

1. **Layer 1 – Biometric:** Face recognition & liveness detection (ArcFace/FaceNet via DeepFace)
2. **Layer 2 – Steganographic Token:** GAN generates an image embedding an encrypted session token
3. **Layer 3 – Dynamic PIN:** User provides specific digits of their PIN (positions determined by hidden data)

## Frontend Routes

- `/` — Initiate Transaction
- `/verify-face` — Biometric facial recognition
- `/verify-pin` — Dynamic PIN verification
- `/success` — Transaction success

## API Endpoints (defined in api.py)

- `POST /auth/register` — Register user with face + PIN
- `POST /transaction/initiate` — Start a transaction (face auth + stego generation)
- `POST /transaction/verify` — Verify dynamic PIN digits
- `GET /health` — Health check

## Development

### Frontend
```bash
cd frontend && pnpm install
cd frontend && pnpm dev   # runs on port 5000
```

### Backend (optional — frontend works in standalone demo mode)
```bash
pip install -r requirements.txt
# Use SecureStegoUPI.untrained() for development without trained model
```

## Deployment

Configured as a **static site** deployment:
- Build: `cd frontend && pnpm build`
- Public dir: `frontend/dist`
