"""
upi/database.py
SQLite persistence for users, face embeddings, transactions, and PIN sessions.
Uses Python's built-in sqlite3 — no extra dependencies.
"""

import base64
import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    pin_hash        TEXT NOT NULL,
    pin_length      INTEGER NOT NULL,
    created_at      INTEGER NOT NULL,
    locked_until    INTEGER DEFAULT 0,
    failed_attempts INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS face_embeddings (
    user_id    TEXT PRIMARY KEY,
    embedding  TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS registration_macs (
    user_id   TEXT PRIMARY KEY,
    macs_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id         TEXT PRIMARY KEY,
    sender_upi    TEXT NOT NULL,
    recipient_upi TEXT NOT NULL,
    amount_rupees REAL NOT NULL,
    timestamp     INTEGER NOT NULL,
    status        TEXT NOT NULL,
    session_token BLOB NOT NULL,
    auth_attempts INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pin_sessions (
    tx_id               TEXT PRIMARY KEY,
    challenge_positions TEXT NOT NULL,
    expected_macs_json  TEXT NOT NULL,
    created_at          INTEGER NOT NULL
);
"""


class DatabaseManager:
    """
    Single SQLite connection for the whole application.
    Instantiate once; inject into AuthPipeline.

    Args:
        db_path: File path, or ":memory:" for a purely in-memory database.
    """

    def __init__(self, db_path: str = "securestego.db") -> None:
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.info(f"Database ready: {db_path}")

    @contextmanager
    def _tx(self):
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cur.close()

    # ── users ────────────────────────────────────────────────────────────────

    def create_user(self, user_id: str, pin_hash: str, pin_length: int) -> None:
        with self._tx() as c:
            if c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone():
                raise ValueError(f"User already exists: {user_id}")
            c.execute(
                "INSERT INTO users (user_id,pin_hash,pin_length,created_at) VALUES (?,?,?,?)",
                (user_id, pin_hash, pin_length, int(time.time()))
            )

    def get_user(self, user_id: str) -> dict | None:
        with self._tx() as c:
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def is_user_locked(self, user_id: str) -> bool:
        u = self.get_user(user_id)
        return u is not None and int(time.time()) < u.get("locked_until", 0)

    def increment_failed_attempts(self, user_id: str, max_attempts: int,
                                   lockout_secs: int = 300) -> int:
        with self._tx() as c:
            c.execute("UPDATE users SET failed_attempts=failed_attempts+1 WHERE user_id=?", (user_id,))
            row = c.execute("SELECT failed_attempts FROM users WHERE user_id=?", (user_id,)).fetchone()
            n   = row["failed_attempts"]
            if n >= max_attempts:
                c.execute("UPDATE users SET locked_until=? WHERE user_id=?",
                           (int(time.time()) + lockout_secs, user_id))
                logger.warning(f"Account locked: {user_id}")
            return n

    def reset_failed_attempts(self, user_id: str) -> None:
        with self._tx() as c:
            c.execute("UPDATE users SET failed_attempts=0, locked_until=0 WHERE user_id=?", (user_id,))

    # ── face embeddings ──────────────────────────────────────────────────────

    def store_face_embedding(self, user_id: str, embedding: list[float]) -> None:
        with self._tx() as c:
            c.execute(
                """INSERT INTO face_embeddings (user_id,embedding,updated_at) VALUES (?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET embedding=excluded.embedding,
                   updated_at=excluded.updated_at""",
                (user_id, json.dumps(embedding), int(time.time()))
            )

    def load_face_embedding(self, user_id: str) -> list[float] | None:
        with self._tx() as c:
            row = c.execute("SELECT embedding FROM face_embeddings WHERE user_id=?", (user_id,)).fetchone()
            return json.loads(row["embedding"]) if row else None

    # ── registration MACs ────────────────────────────────────────────────────

    def store_registration_macs(self, user_id: str, macs: dict[int, bytes]) -> None:
        """Store per-position MACs built at registration time."""
        serialised = {str(k): base64.b64encode(v).decode() for k, v in macs.items()}
        with self._tx() as c:
            c.execute(
                """INSERT INTO registration_macs (user_id, macs_json) VALUES (?,?)
                   ON CONFLICT(user_id) DO UPDATE SET macs_json=excluded.macs_json""",
                (user_id, json.dumps(serialised))
            )

    def load_registration_macs(self, user_id: str) -> dict[int, bytes] | None:
        """Load per-position registration MACs. Returns {pos: bytes} or None."""
        with self._tx() as c:
            row = c.execute("SELECT macs_json FROM registration_macs WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                return None
            raw = json.loads(row["macs_json"])
            return {int(k): base64.b64decode(v) for k, v in raw.items()}

    # ── transactions ─────────────────────────────────────────────────────────

    def save_transaction(self, tx) -> None:
        with self._tx() as c:
            c.execute(
                """INSERT INTO transactions
                   (tx_id,sender_upi,recipient_upi,amount_rupees,timestamp,status,session_token,auth_attempts)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(tx_id) DO UPDATE SET
                   status=excluded.status, auth_attempts=excluded.auth_attempts""",
                (tx.tx_id, tx.sender_upi, tx.recipient_upi, tx.amount_rupees,
                 tx.timestamp, tx.status.value, tx.session_token, tx.auth_attempts)
            )

    def load_transaction(self, tx_id: str):
        from upi.transaction import Transaction, TransactionStatus
        with self._tx() as c:
            row = c.execute("SELECT * FROM transactions WHERE tx_id=?", (tx_id,)).fetchone()
            if not row:
                return None
            return Transaction(
                tx_id         = row["tx_id"],
                sender_upi    = row["sender_upi"],
                recipient_upi = row["recipient_upi"],
                amount_rupees = row["amount_rupees"],
                timestamp     = row["timestamp"],
                status        = TransactionStatus(row["status"]),
                session_token = bytes(row["session_token"]),
                auth_attempts = row["auth_attempts"],
            )

    # ── PIN sessions ─────────────────────────────────────────────────────────

    def save_pin_session(self, tx_id: str, challenge_positions: list[int],
                          expected_macs: dict[int, bytes]) -> None:
        macs_json = json.dumps({str(k): base64.b64encode(v).decode() for k, v in expected_macs.items()})
        with self._tx() as c:
            c.execute(
                """INSERT INTO pin_sessions (tx_id,challenge_positions,expected_macs_json,created_at)
                   VALUES (?,?,?,?)
                   ON CONFLICT(tx_id) DO UPDATE SET
                   challenge_positions=excluded.challenge_positions,
                   expected_macs_json=excluded.expected_macs_json""",
                (tx_id, json.dumps(challenge_positions), macs_json, int(time.time()))
            )

    def load_pin_session(self, tx_id: str) -> tuple[list[int], dict[int, bytes]] | None:
        with self._tx() as c:
            row = c.execute("SELECT * FROM pin_sessions WHERE tx_id=?", (tx_id,)).fetchone()
            if not row:
                return None
            positions = json.loads(row["challenge_positions"])
            macs      = {int(k): base64.b64decode(v)
                         for k, v in json.loads(row["expected_macs_json"]).items()}
            return positions, macs

    def delete_pin_session(self, tx_id: str) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM pin_sessions WHERE tx_id=?", (tx_id,))

    def close(self) -> None:
        self._conn.close()
