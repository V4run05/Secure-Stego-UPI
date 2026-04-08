# SecureStego-UPI

A novel multi-factor UPI payment authentication system using Coverless GAN Steganography to create tamper-evident transaction channels.

## Architecture

### Frontend (React + Vite)
- **Framework:** React 18 (TypeScript)
- **Build Tool:** Vite 6
- **Styling:** Tailwind CSS 4, Lucide React
- **Routing:** React Router 7
- **Animations:** Motion (Framer Motion)
- **Notifications:** Sonner (toast)
- **Package Manager:** pnpm
- **Location:** `frontend/`
- **Dev Port:** 5000
- **Proxy:** `/api/*` → `http://localhost:8000` (Vite proxy in `vite.config.ts`)

### Backend (Python — AI/ML)
- **HTTP Server:** Flask (`run_backend.py`) on port 8000
- **Deep Learning:** PyTorch (DCGAN architecture)
- **Face Auth:** DeepFace (optional — mock mode without it)
- **Cryptography:** pycryptodome (AES-128-CBC), bcrypt
- **Database:** SQLite via `upi/database.py`

## Project Structure

```
SecureStego-UPI/
├── core/                    # GAN Backbone
│   ├── models.py            # Generator, Discriminator, Extractor
│   ├── crypto.py            # AES encryption + bit-tensor conversion
│   ├── train.py             # GAN training loops
│   └── evaluate.py          # BER, FID metrics
├── upi/                     # UPI Application Layer
│   ├── auth_pipeline.py     # Face→Stego→PIN orchestration (audit logging)
│   ├── face_auth.py         # Biometric verification
│   ├── dynamic_pin.py       # HMAC-based challenge generation
│   ├── transaction.py       # Transaction data model
│   └── database.py          # SQLite (users, face_embeddings, transactions,
│                            #         pin_sessions, registration_macs, audit_log)
├── frontend/
│   ├── src/app/
│   │   ├── components/
│   │   │   ├── InitiateTransaction.tsx   # Home / payment initiation
│   │   │   ├── FacialRecognition.tsx     # Layer 1 — biometric (real webcam)
│   │   │   ├── PinVerification.tsx       # Layer 2 — dynamic PIN
│   │   │   ├── TransactionSuccess.tsx    # Receipt display
│   │   │   ├── Registration.tsx          # 4-step account creation
│   │   │   ├── TransactionHistory.tsx    # Transaction list
│   │   │   ├── WebcamCapture.tsx         # react-webcam wrapper
│   │   │   └── ErrorBoundary.tsx         # React error boundary
│   │   ├── context/UserContext.tsx       # User state + sessionStorage
│   │   ├── hooks/
│   │   │   ├── useSessionTimeout.ts      # Auto-logout on inactivity
│   │   │   └── useOnlineStatus.ts        # Online/offline detection
│   │   ├── services/api.ts               # All API calls (/api/* prefix)
│   │   ├── routes.tsx                    # React Router routes
│   │   └── App.tsx                       # Root (UserProvider + ErrorBoundary + Toaster)
│   └── vite.config.ts
├── run_backend.py            # Flask HTTP server (port 8000)
├── cli.py                    # Click + Rich verbose CLI demo
├── api.py                    # SecureStegoUPI public API class
└── requirements.txt
```

## Authentication Flow

1. **Layer 1 – Biometric:** Real webcam capture → face embedding via DeepFace
2. **Layer 2 – Steganographic Token:** GAN embeds encrypted session token in cover image
3. **Layer 3 – Dynamic PIN:** Challenged PIN positions determined by hidden session token

## Frontend Routes

| Route | Component | Description |
|---|---|---|
| `/` | InitiateTransaction | Amount + payee selection |
| `/register` | Registration | 4-step account creation |
| `/history` | TransactionHistory | Past transactions |
| `/verify-face` | FacialRecognition | Webcam face capture + API call |
| `/verify-pin` | PinVerification | Dynamic PIN pad from backend challenge |
| `/success` | TransactionSuccess | Receipt from sessionStorage |

## API Endpoints (Flask — run_backend.py)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check + device info |
| POST | `/auth/register` | Register user with face + PIN |
| POST | `/transaction/initiate` | Face auth + stego + PIN challenge |
| POST | `/transaction/verify` | Verify dynamic PIN digits |
| GET | `/transactions/list?user_id=...` | Transaction history |

## sessionStorage Keys

- `currentUser` — logged-in user object
- `pendingTransaction` — amount + recipient before face auth
- `txChallenge` — backend's initiate response (pin_positions, tx_id, stego, etc.)
- `receipt` — backend's verify response (shown on success page)

## Demo / Offline Mode

When the backend is unreachable, the frontend falls back to demo mode:
- PIN challenge uses hardcoded positions `[1, 3, 5]`
- Any digit is accepted for verification
- Status badge shows "Demo Mode" in yellow

## Development

### Frontend
```bash
cd frontend && pnpm install
cd frontend && pnpm dev   # port 5000
```

### Backend (optional)
```bash
pip install -r requirements.txt
python run_backend.py     # port 8000
```

### CLI Demo
```bash
python cli.py health
python cli.py register --user-id alice@upi --pin 123456 --face-image face.jpg
python cli.py initiate --user-id alice@upi --recipient bob@upi --amount 100 --face-image face.jpg
python cli.py verify   --tx-id <uuid> --pin-digits "1:4,3:7,5:2"
python cli.py list-txs --user-id alice@upi
```

## Security Properties

- PIN never stored plaintext or transmitted over network
- Per-position HMAC chain binds submitted digits to a specific transaction
- GAN stego image encodes encrypted 16-byte compact token
- Face embeddings stored, raw images discarded
- Failed attempts tracked with configurable account lockout
- PIN sessions have TTL (default 300s) — expired sessions rejected
- All operations emit structured audit log entries (never including secrets)
- Timing-safe comparisons (`hmac.compare_digest`) throughout
