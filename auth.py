"""
auth.py — authentication backed by Appwrite TablesDB (SDK v24)
--------------------------------------------------------------------------
* Passwords hashed with PBKDF2-HMAC-SHA256 (stdlib, no extra deps).
* Uses the non-deprecated TablesDB service with list_rows / create_row /
  get_row / delete_row instead of the deprecated Databases methods.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.query import Query
from appwrite.services.tables_db import TablesDB

# ── Config ────────────────────────────────────────────────────────────────────
APPWRITE_ENDPOINT   = os.getenv("APPWRITE_ENDPOINT",   "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID", "")
APPWRITE_API_KEY    = os.getenv("APPWRITE_API_KEY",    "")
DATABASE_ID         = os.getenv("APPWRITE_DATABASE_ID",         "")
USERS_COLLECTION    = os.getenv("APPWRITE_USERS_COLLECTION",    "users")
TOKENS_COLLECTION   = os.getenv("APPWRITE_TOKENS_COLLECTION",   "tokens")

_PBKDF2_ITERATIONS = 120_000


def _db() -> TablesDB:
    client = Client()
    (client
        .set_endpoint(APPWRITE_ENDPOINT)
        .set_project(APPWRITE_PROJECT_ID)
        .set_key(APPWRITE_API_KEY))
    return TablesDB(client)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Helpers to safely extract field from Row/Document v24 ────────────────────
def _field(doc, key: str):
    """Get a user-defined field from an Appwrite v24 Row/Document object."""
    if hasattr(doc, 'data') and isinstance(doc.data, dict):
        return doc.data.get(key)
    # Fallback: try direct attribute
    if hasattr(doc, 'data'):
        return getattr(doc.data, key, None)
    # If doc itself is dict-like
    if isinstance(doc, dict):
        return doc.get(key)
    return None


def _doc_to_dict(doc) -> dict[str, Any]:
    """Convert Row/Document → plain dict for internal use."""
    if hasattr(doc, 'data') and isinstance(doc.data, dict):
        return dict(doc.data)
    if isinstance(doc, dict):
        return dict(doc)
    try:
        return dict(doc.data)
    except Exception:
        return {}


# ── Password hashing ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected)


# ── User operations ───────────────────────────────────────────────────────────
def load_users() -> dict[str, Any]:
    """Compatibility shim: returns {email: record_dict} for _seed_demo check."""
    try:
        result = _db().list_rows(
            DATABASE_ID, USERS_COLLECTION, queries=[Query.limit(100)]
        )
        return {_field(doc, "email"): _doc_to_dict(doc) for doc in result.rows}
    except (AppwriteException, AttributeError):
        return {}


def register(name: str, email: str, password: str) -> dict[str, Any]:
    email = email.strip().lower()
    name  = name.strip()

    if len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Enter a valid email address")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    db = _db()

    # Duplicate email check
    existing = db.list_rows(
        DATABASE_ID, USERS_COLLECTION,
        queries=[Query.equal("email", email), Query.limit(1)]
    )
    if existing.total > 0:
        raise ValueError("An account with this email already exists")

    record = {
        "name":          name,
        "email":         email,
        "password_hash": hash_password(password),
        "created_at":    _now(),
    }
    db.create_row(DATABASE_ID, USERS_COLLECTION, ID.unique(), record)
    return _public_user(record)


def login(email: str, password: str) -> tuple[str, dict[str, Any]]:
    email = email.strip().lower()
    db    = _db()

    result = db.list_rows(
        DATABASE_ID, USERS_COLLECTION,
        queries=[Query.equal("email", email), Query.limit(1)]
    )
    if result.total == 0:
        raise ValueError("Incorrect email or password")

    record = _doc_to_dict(result.rows[0])
    if not verify_password(password, record.get("password_hash", "")):
        raise ValueError("Incorrect email or password")

    # token = 32 hex chars — fits Appwrite doc-ID 36-char limit
    token = secrets.token_hex(16)
    db.create_row(
        DATABASE_ID, TOKENS_COLLECTION, token,
        {"token": token, "email": email, "created_at": _now()}
    )
    return token, _public_user(record)


def logout(token: str) -> None:
    try:
        _db().delete_row(DATABASE_ID, TOKENS_COLLECTION, token)
    except AppwriteException:
        pass


def get_user_by_token(token: str) -> dict[str, Any] | None:
    db = _db()
    try:
        tok_doc = db.get_row(DATABASE_ID, TOKENS_COLLECTION, token)
        email = _field(tok_doc, "email")
    except AppwriteException:
        return None

    if not email:
        return None

    result = db.list_rows(
        DATABASE_ID, USERS_COLLECTION,
        queries=[Query.equal("email", email), Query.limit(1)]
    )
    if result.total == 0:
        return None
    return _public_user(_doc_to_dict(result.rows[0]))


def _public_user(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name":       record.get("name", ""),
        "email":      record.get("email", ""),
        "created_at": record.get("created_at"),
    }