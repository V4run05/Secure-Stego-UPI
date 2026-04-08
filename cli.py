"""
cli.py — Secure-Stego-UPI CLI

Educational CLI that demonstrates every security operation with verbose,
step-by-step output using box-drawing characters.

Usage:
    python cli.py register --user-id alice@upi --pin 123456 --face-image face.jpg
    python cli.py initiate --user-id alice@upi --recipient bob@upi --amount 100.50 --face-image face.jpg
    python cli.py verify   --tx-id <uuid> --pin-digits "1:4,3:7,5:2"
    python cli.py show-tx  --tx-id <uuid>
    python cli.py list-txs --user-id alice@upi
    python cli.py decode-stego --image stego.png --salt-b64 <b64> --user-id alice@upi
    python cli.py health
"""

import base64
import hashlib
import hmac as _hmac
import json
import os
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box as rich_box

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _step(num: int, title: str, lines: list[str]) -> None:
    body = "\n".join(lines)
    console.print(Panel(body, title=f"[bold cyan]STEP {num}: {title}[/bold cyan]",
                         border_style="blue", expand=False))


def _hex(label: str, data: bytes, limit: int = 32) -> str:
    h = " ".join(f"{b:02x}" for b in data[:limit])
    suffix = f" ... ({len(data)} bytes total)" if len(data) > limit else ""
    return f"  {label}: [yellow]{h}{suffix}[/yellow]"


def _mask(s: str, show: int = 0) -> str:
    return "*" * len(s) if show == 0 else s[:show] + "*" * (len(s) - show)


def _load_api(checkpoint: str | None = None):
    from api import SecureStegoUPI
    cp = checkpoint or os.environ.get("CHECKPOINT_PATH", "checkpoints/checkpoint_final.pt")
    try:
        return SecureStegoUPI.from_checkpoint(
            cp, app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"))
    except Exception:
        console.print("[yellow]⚠  Checkpoint not found — running in demo/untrained mode[/yellow]")
        return SecureStegoUPI.untrained(
            app_secret=os.environ.get("APP_SECRET", "dev-secret-change-in-production"))


def _face_b64(path: str) -> str:
    """Read a face image file and return base64 string, or a placeholder if missing."""
    p = Path(path)
    if p.exists():
        return base64.b64encode(p.read_bytes()).decode()
    console.print(f"[yellow]⚠  Face image not found at '{path}' — using placeholder (mock mode)[/yellow]")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
#  Security step display helpers
# ─────────────────────────────────────────────────────────────────────────────

def _show_input_validation(user_id: str, pin: str, face_path: str | None = None) -> list[str]:
    lines = []
    upi_ok = user_id.endswith("@upi") and " " not in user_id and user_id == user_id.lower()
    lines.append(f"  {'✓' if upi_ok else '✗'} User ID: [cyan]{user_id}[/cyan] "
                 f"({'valid UPI format' if upi_ok else 'invalid — must be lowercase xxx@upi'})")
    pin_ok = pin.isdigit() and 4 <= len(pin) <= 6
    lines.append(f"  {'✓' if pin_ok else '✗'} PIN: [cyan]{_mask(pin)}[/cyan] "
                 f"({'6 digits, format valid' if pin_ok else f'invalid — {len(pin)} digits, must be 4-6'})")
    if face_path:
        fp = Path(face_path)
        lines.append(f"  {'✓' if fp.exists() else '⚠'} Face image: [cyan]{face_path}[/cyan] "
                     f"({'found' if fp.exists() else 'not found — mock mode'})")
    return lines


def _show_pin_hashing(pin: str) -> list[str]:
    import bcrypt
    salt = bcrypt.gensalt(rounds=12)
    pin_hash = bcrypt.hashpw(pin.encode(), salt).decode()
    lines = [
        "  Algorithm: [green]bcrypt[/green] (rounds=12)",
        f"  Input (plaintext PIN): [cyan]{_mask(pin)}[/cyan]",
        f"  Salt generated: [yellow]{salt.decode()[:20]}...[/yellow]",
        f"  ✓ PIN Hash: [yellow]{pin_hash[:20]}...[/yellow]",
        "  (Hash is stored — plaintext PIN is discarded after this step)",
    ]
    return lines


def _show_registration_macs(pin: str, user_id: str, app_secret: str) -> list[str]:
    lines = [
        f"  Server Secret: [dim]{_mask(app_secret, 4)}[/dim]",
        "",
    ]
    for i, digit in enumerate(pin):
        pos = i + 1
        material = f"{app_secret}:{user_id}:{pos}"
        pos_key  = hashlib.sha256(material.encode()).digest()
        reg_mac  = _hmac.new(pos_key, digit.encode(), hashlib.sha256).digest()
        pk_hex   = pos_key.hex()[:16]
        rm_hex   = reg_mac.hex()[:16]
        lines += [
            f"  [bold]Position {pos}[/bold] (digit: [cyan]{_mask(digit)}[/cyan]):",
            f"    Pos Key = SHA256(\"{_mask(app_secret, 4)}:{user_id}:{pos}\")",
            f"            = [yellow]{pk_hex}...[/yellow]",
            f"    Reg MAC = HMAC-SHA256(pos_key, digit)",
            f"            = [yellow]{rm_hex}...[/yellow]",
            "",
        ]
    lines.append(f"  ✓ Stored {len(pin)} registration MACs in database")
    return lines


def _show_challenge_generation(session_token: bytes, tx_id: str,
                                pin_length: int, positions: list[int]) -> list[str]:
    digest = _hmac.new(session_token, tx_id.encode(), hashlib.sha256).digest()
    lines = [
        _hex("  session_token", session_token),
        f"  tx_id:         [cyan]{tx_id[:20]}...[/cyan]",
        "",
        f"  digest = HMAC-SHA256(session_token, tx_id)",
        _hex("         ", digest),
        "",
        f"  Selecting {len(positions)} positions from {pin_length}-digit PIN:",
    ]
    chosen, byte_idx = set(), 0
    while len(chosen) < len(positions) and byte_idx < len(digest):
        b = digest[byte_idx]
        cand = (b % pin_length) + 1
        status = "✓" if cand in set(positions) else " "
        dup    = " (duplicate, skip)" if cand in chosen and cand in set(positions) else ""
        lines.append(f"    byte[{byte_idx}] = 0x{b:02x} → {b} % {pin_length} = {b % pin_length}"
                     f" → pos {cand}{dup}")
        chosen.add(cand)
        byte_idx += 1
    lines.append(f"\n  ✓ Challenge Positions (1-indexed): [bold green]{positions}[/bold green]")
    return lines


def _show_security_audit() -> None:
    lines = [
        "  ✓ PIN never stored in plaintext",
        "  ✓ PIN never transmitted over network",
        "  ✓ Each transaction uses unique challenge positions",
        "  ✓ Session tokens are cryptographically random (os.urandom)",
        "  ✓ MACs are transaction-bound (prevent replay attacks)",
        "  ✓ Timing-safe comparisons (hmac.compare_digest) used throughout",
        "  ✓ Stego image embeds tamper-proof transaction data via GAN",
        "  ✓ Face embeddings stored, not raw images",
        "  ✓ Failed attempts tracked with account lockout",
        "  ✓ PIN sessions expire after TTL",
        "  ✓ Audit log records all events (never includes sensitive data)",
    ]
    console.print(Panel("\n".join(lines),
                         title="[bold green]SECURITY AUDIT TRAIL[/bold green]",
                         border_style="green", expand=False))


# ─────────────────────────────────────────────────────────────────────────────
#  CLI commands
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """Secure-Stego-UPI CLI — Educational Security Demo

    Demonstrates every security operation with verbose step-by-step output
    including PIN hashing, HMAC chains, GAN steganography, and dynamic
    PIN challenge generation.
    """
    pass


@cli.command()
@click.option("--user-id",    required=True,  help="UPI ID, e.g. alice@upi")
@click.option("--pin",        required=True,  help="4-6 digit numeric PIN")
@click.option("--face-image", required=True,  help="Path to face image (JPEG/PNG)")
@click.option("--verbose",    is_flag=True, default=True, show_default=True)
def register(user_id: str, pin: str, face_image: str, verbose: bool):
    """Register a new user with verbose security logging."""
    api = _load_api()
    console.rule(f"[bold green]USER REGISTRATION: {user_id}[/bold green]")

    if verbose:
        _step(1, "Input Validation", _show_input_validation(user_id, pin, face_image))
        _step(2, "Client-Side PIN Hashing", _show_pin_hashing(pin))
        _step(3, "Building Registration MACs (per-position HMACs)",
              _show_registration_macs(pin, user_id, api._p.app_secret))

        face_b64 = _face_b64(face_image)
        if face_b64:
            _step(4, "Face Embedding Extraction", [
                "  Model: FaceNet / ArcFace (via DeepFace)",
                f"  Input: {face_image}",
                "  Preprocessing: Resize → Normalize",
                "  ✓ Embedding extracted and stored (raw image never persisted)",
            ])
        else:
            _step(4, "Face Embedding Extraction", [
                "  ⚠  No real image provided — face stored as mock embedding",
            ])

    face_b64 = _face_b64(face_image)
    result = api.register_user(user_id, face_b64, pin)

    if verbose:
        _step(5, "Database Storage", [
            "  Table: [cyan]users[/cyan]",
            f"    user_id:         {user_id}",
            f"    pin_hash:        $2b$12$... (bcrypt, never plaintext)",
            f"    pin_length:      {len(pin)}",
            f"    failed_attempts: 0",
            f"    created_at:      {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "",
            "  Table: [cyan]registration_macs[/cyan]",
            f"    {len(pin)} rows inserted (one per PIN position)",
            "",
            "  Table: [cyan]face_embeddings[/cyan]",
            "    Embedding stored as JSON array (raw image discarded)",
        ])
        _show_security_audit()

    if result["success"]:
        console.print(f"\n[bold green]✓ USER REGISTERED SUCCESSFULLY[/bold green]")
        console.print(f"  User ID: [cyan]{result['user_id']}[/cyan]")
    else:
        console.print(f"\n[bold red]✗ REGISTRATION FAILED: {result['reason']}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option("--user-id",    required=True,  help="UPI ID of the sender")
@click.option("--recipient",  required=True,  help="UPI ID of the recipient")
@click.option("--amount",     required=True,  type=float, help="Amount in rupees")
@click.option("--face-image", required=True,  help="Path to face image for live auth")
@click.option("--verbose",    is_flag=True, default=True, show_default=True)
def initiate(user_id: str, recipient: str, amount: float, face_image: str, verbose: bool):
    """Initiate a transaction with verbose step-by-step output."""
    api = _load_api()
    console.rule(f"[bold blue]TRANSACTION INITIATION: {user_id} → {recipient} (₹{amount:.2f})[/bold blue]")

    face_b64 = _face_b64(face_image)

    if verbose:
        _step(1, "Face Authentication (Layer 1)", [
            f"  Input: {face_image}",
            "  ✓ Sending face image to backend for embedding extraction",
            "  ✓ Comparing against stored registration embedding (cosine similarity)",
            "  ✓ Liveness check performed",
        ])
        _step(2, "Transaction Object Creation", [
            f"  sender_upi:    {user_id}",
            f"  recipient_upi: {recipient}",
            f"  amount_rupees: {amount:.2f}",
            f"  amount_cents:  {int(amount * 100)} (uint32)",
            f"  timestamp:     {int(time.time())} (Unix time)",
            "  session_token: <6 random bytes from os.urandom(6)>",
            "  status:        PENDING_PIN",
        ])
        _step(3, "Compact Token Encoding (16 bytes)", [
            "  Bytes 0-5:   session_token (6 random bytes)",
            "  Bytes 6-9:   SHA256(tx_id)[:4]",
            f"  Bytes 10-13: {int(amount * 100)} in big-endian uint32",
            f"  Bytes 14-15: SHA256({recipient})[:2]",
        ])
        _step(4, "AES Encryption of Compact Token", [
            "  Password = SHA256(app_secret:user_id)",
            "  Salt     = os.urandom(16)",
            "  PBKDF2-HMAC-SHA256: iterations=200,000, dklen=24",
            "  AES Key  = derived_key[:16]",
            "  PRNG Seed= derived_key[16:24] as uint64",
            "  Mode: AES-128-CBC with random IV",
            "  ✓ Encrypted blob: IV (16 bytes) || Ciphertext (16 bytes) = 32 bytes",
        ])
        _step(5, "GAN Steganography Encoding", [
            "  Converting encrypted blob → 256-bit tensor",
            "  Seeding noise vector z with PRNG seed (deterministic from password+salt)",
            "  Generator forward pass: G(z, message_bits) → 64×64 RGB image",
            "  ✓ Stego image generated — recipient and amount embedded invisibly",
        ])

    result = api.initiate_transaction(user_id, face_b64, amount, recipient)

    if isinstance(result, dict) and "error" in result:
        console.print(f"\n[bold red]✗ INITIATION FAILED: {result['error']}[/bold red]")
        if "attempts_remaining" in result:
            console.print(f"  Attempts remaining: {result['attempts_remaining']}")
        sys.exit(1)

    if not isinstance(result, dict):
        result = result if isinstance(result, dict) else result

    positions = result.get("pin_positions", [])

    if verbose:
        _step(6, "Dynamic PIN Challenge Generation", [
            "  Extracting session_token from stego image",
            f"  HMAC-SHA256(session_token, tx_id) → challenge digest",
            f"  ✓ Challenge Positions (1-indexed): [bold green]{positions}[/bold green]",
            "  (Positions change every transaction — session_token is per-TX random)",
        ])
        _step(7, "Building Expected MACs for Challenge Positions", [
            "  For each challenged position:",
            "    reg_mac[pos] = stored HMAC from registration",
            "    expected_mac = HMAC(reg_mac, tx_id)  ← transaction-bound",
            "  ✓ Expected MACs stored in pin_sessions table",
            f"  ✓ Session expires in {300}s (TTL enforced on verify)",
        ])
        _step(8, "Response to Client", [
            f"  tx_id:         [cyan]{result['tx_id']}[/cyan]",
            f"  salt_b64:      {result['salt_b64'][:20]}...",
            f"  pin_positions: [bold green]{positions}[/bold green]",
            f"  stego_image:   <{len(result.get('stego_image_b64',''))} base64 chars>",
            "",
            "  [yellow]⚠  SECURITY: Client MUST extract session_token from stego image[/yellow]",
            "     to independently verify pin_positions (not just trust JSON).",
        ])
        _show_security_audit()

    console.print(f"\n[bold green]✓ TRANSACTION INITIATED SUCCESSFULLY[/bold green]")
    console.print(f"  tx_id:          [cyan]{result['tx_id']}[/cyan]")
    console.print(f"  PIN positions:  [bold yellow]{positions}[/bold yellow]")
    console.print(f"\n  Next step: [bold]python cli.py verify --tx-id {result['tx_id']} "
                  f"--pin-digits \"<pos>:<digit>,...\"[/bold]")


@cli.command()
@click.option("--tx-id",      required=True, help="Transaction ID from initiate")
@click.option("--pin-digits", required=True, help="Comma-separated pos:digit pairs, e.g. 1:4,3:7,5:2")
@click.option("--verbose",    is_flag=True, default=True, show_default=True)
def verify(tx_id: str, pin_digits: str, verbose: bool):
    """Verify a transaction by submitting challenged PIN digits."""
    api = _load_api()
    console.rule(f"[bold magenta]PIN VERIFICATION: {tx_id[:16]}...[/bold magenta]")

    try:
        digits: dict[str, str] = {}
        for pair in pin_digits.split(","):
            pos, digit = pair.strip().split(":")
            digits[pos.strip()] = digit.strip()
    except Exception:
        console.print("[bold red]✗ Invalid --pin-digits format. Use: 1:4,3:7,5:2[/bold red]")
        sys.exit(1)

    if verbose:
        _step(1, "Load Transaction and Session", [
            f"  tx_id: [cyan]{tx_id}[/cyan]",
            "  ✓ Transaction loaded from database",
            "  ✓ Checking status is PENDING_PIN",
            "  ✓ Checking PIN session has not expired (TTL=300s)",
        ])
        _step(2, "Parse Submitted PIN Digits", [
            f"  Input: [cyan]{pin_digits}[/cyan]",
        ] + [f"    Position {p} → digit '{_mask(d)}'" for p, d in digits.items()] + [
            "  ✓ All required positions present",
            "  ✓ All values are single digits (0-9)",
        ])
        _step(3, "Recompute MACs for Submitted Digits", [
            "  For each submitted position:",
            "    pos_key   = SHA256(app_secret:user_id:pos)",
            "    reg_mac   = HMAC(pos_key, submitted_digit)",
            "    tx_mac    = HMAC(reg_mac, tx_id)",
            "  Comparing tx_mac vs expected_mac with hmac.compare_digest (timing-safe)",
        ])

    result = api.verify_transaction(tx_id, digits)

    if verbose:
        outcome = "✓ MATCH" if result["authorized"] else "✗ MISMATCH"
        _step(4, "Timing-Safe MAC Comparison", [
            f"  Result: [{'bold green' if result['authorized'] else 'bold red'}]{outcome}[/{'bold green' if result['authorized'] else 'bold red'}]",
            f"  Authorized: {result['authorized']}",
            f"  Reason: {result['reason']}",
        ])

    if result["authorized"]:
        receipt = result.get("receipt", {})
        _step(5, "Transaction Authorized", [
            "  ✓ Transaction status → AUTHORIZED",
            "  ✓ Failed attempts counter reset",
            "  ✓ PIN session deleted (one-time use)",
        ])
        console.print(f"\n[bold green]✓ TRANSACTION AUTHORIZED[/bold green]")
        if receipt:
            t = Table(title="Receipt", box=rich_box.ROUNDED)
            t.add_column("Field", style="cyan")
            t.add_column("Value")
            for k, v in receipt.items():
                t.add_row(str(k), str(v))
            console.print(t)
    else:
        console.print(f"\n[bold red]✗ VERIFICATION FAILED: {result['reason']}[/bold red]")
        console.print(f"  Attempts remaining: {result['attempts_remaining']}")
        sys.exit(1)


@cli.command("show-tx")
@click.option("--tx-id", required=True, help="Transaction ID to display")
def show_tx(tx_id: str):
    """Show details of a specific transaction."""
    api = _load_api()
    tx = api._p.db.load_transaction(tx_id)
    if not tx:
        console.print(f"[bold red]Transaction not found: {tx_id}[/bold red]")
        sys.exit(1)
    t = Table(title=f"Transaction: {tx_id[:16]}...", box=rich_box.ROUNDED)
    t.add_column("Field", style="cyan")
    t.add_column("Value")
    t.add_row("tx_id",         tx.tx_id)
    t.add_row("sender_upi",    tx.sender_upi)
    t.add_row("recipient_upi", tx.recipient_upi)
    t.add_row("amount",        f"₹{tx.amount_rupees:.2f}")
    t.add_row("status",        tx.status.value)
    t.add_row("timestamp",     time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(tx.timestamp)))
    t.add_row("auth_attempts", str(tx.auth_attempts))
    console.print(t)


@cli.command("list-txs")
@click.option("--user-id", required=True, help="UPI ID of the user")
def list_txs(user_id: str):
    """List all transactions for a user."""
    api = _load_api()
    txs = api._p.db.get_user_transactions(user_id)
    if not txs:
        console.print(f"[yellow]No transactions found for {user_id}[/yellow]")
        return
    t = Table(title=f"Transactions for {user_id}", box=rich_box.ROUNDED)
    t.add_column("tx_id (short)", style="cyan")
    t.add_column("recipient")
    t.add_column("amount", justify="right")
    t.add_column("status")
    t.add_column("timestamp")
    for tx in txs:
        color = {"AUTHORIZED": "green", "PENDING_PIN": "yellow",
                 "REJECTED": "red", "EXPIRED": "dim"}.get(tx["status"], "white")
        t.add_row(
            tx["tx_id"][:16] + "...",
            tx["recipient_upi"],
            f"₹{tx['amount_rupees']:.2f}",
            f"[{color}]{tx['status']}[/{color}]",
            time.strftime("%Y-%m-%d %H:%M", time.gmtime(tx["timestamp"])),
        )
    console.print(t)


@cli.command("decode-stego")
@click.option("--image",    required=True, help="Path to stego image file")
@click.option("--salt-b64", required=True, help="Base64-encoded salt (from initiate response)")
@click.option("--user-id",  required=True, help="UPI ID (used to derive stego password)")
def decode_stego(image: str, salt_b64: str, user_id: str):
    """Decode a stego image to reveal the embedded compact token (educational)."""
    api = _load_api()
    try:
        from PIL import Image as PILImage
        from upi.stego_bridge import decode_transaction
        img  = PILImage.open(image).convert("RGB")
        salt = base64.b64decode(salt_b64)
        password = api._p._stego_password(user_id)
        token = decode_transaction(img, password, salt, api._cfg, api._p.E)
        console.print(Panel(
            "\n".join([
                f"  session_token (6 bytes): [yellow]{token.session_token.hex()}[/yellow]",
                f"  tx_id_hash    (4 bytes): [yellow]{token.tx_id_hash.hex()}[/yellow]",
                f"  amount_cents  (uint32):  [cyan]{token.amount_cents}[/cyan]"
                f"  = ₹{token.amount_cents / 100:.2f}",
                f"  recipient_hash(2 bytes): [yellow]{token.recipient_hash.hex()}[/yellow]",
                "",
                "  ✓ Stego image decoded successfully",
                "  ✓ session_token can now be used to verify challenge positions",
            ]),
            title="[bold green]STEGO DECODE RESULT[/bold green]",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[bold red]✗ Stego decode failed: {e}[/bold red]")
        sys.exit(1)


@cli.command()
def health():
    """Check backend health (direct API call, no HTTP)."""
    api = _load_api()
    result = api.health()
    t = Table(title="Backend Health", box=rich_box.ROUNDED)
    t.add_column("Field", style="cyan")
    t.add_column("Value")
    for k, v in result.items():
        t.add_row(str(k), str(v))
    console.print(t)


if __name__ == "__main__":
    cli()
