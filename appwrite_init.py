"""
appwrite_init.py — One-time setup script for TN StuScholar
------------------------------------------------------------
Run once:  python appwrite_init.py

Creates all required attributes and indexes on your existing Appwrite
collections. Collections must already exist (created in the Dashboard).
Safe to re-run: skips anything that already exists.

If you need to create collections too, add the 'collections.write' scope
to your API key in Appwrite Dashboard → Settings → API Keys.
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import os, sys, time
from dotenv import load_dotenv
load_dotenv()

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

# ── Config ────────────────────────────────────────────────────────────────────
ENDPOINT   = os.getenv("APPWRITE_ENDPOINT",   "https://cloud.appwrite.io/v1")
PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID", "")
API_KEY    = os.getenv("APPWRITE_API_KEY",    "")
DB_ID      = os.getenv("APPWRITE_DATABASE_ID", "")

USERS_COL  = os.getenv("APPWRITE_USERS_COLLECTION",  "users")
TOKENS_COL = os.getenv("APPWRITE_TOKENS_COLLECTION", "tokens")
APPS_COL   = os.getenv("APPWRITE_APPS_COLLECTION",   "applications")

# ── Appwrite client ───────────────────────────────────────────────────────────
client = Client()
client.set_endpoint(ENDPOINT).set_project(PROJECT_ID).set_key(API_KEY)
db = Databases(client)


def ok(msg):    print(f"  ✓ {msg}")
def skip(msg):  print(f"  ► {msg} (already exists)")
def section(m): print(f"\n[{m}]")
def err(msg):   print(f"  ✗ ERROR: {msg}")


def is_already_exists(e: AppwriteException) -> bool:
    msg = str(e).lower()
    return "already exists" in msg or "409" in msg


# ── Collection helpers ────────────────────────────────────────────────────────
def ensure_collection(col_id: str, name: str) -> None:
    try:
        db.create_collection(DB_ID, col_id, name,
                             permissions=["read(\"any\")", "write(\"any\")"],
                             document_security=False)
        ok(f"Collection '{col_id}' created")
        time.sleep(1)
    except AppwriteException as e:
        if is_already_exists(e):
            skip(f"Collection '{col_id}'")
        else:
            err(f"Collection '{col_id}': {e}  ← needs 'collections.write' scope on API key")


def str_attr(col_id, key, size, required):
    try:
        db.create_string_attribute(DB_ID, col_id, key, size, required, array=False)
        ok(f"attr '{key}' (String, {size})")
        time.sleep(0.5)
    except AppwriteException as e:
        if is_already_exists(e):
            skip(f"attr '{key}'")
        else:
            err(f"attr '{key}': {e}")


def int_attr(col_id, key, required):
    try:
        db.create_integer_attribute(DB_ID, col_id, key, required)
        ok(f"attr '{key}' (Integer)")
        time.sleep(0.5)
    except AppwriteException as e:
        if is_already_exists(e):
            skip(f"attr '{key}'")
        else:
            err(f"attr '{key}': {e}")


def ensure_index(col_id, index_key, index_type, attributes):
    try:
        db.create_index(DB_ID, col_id, index_key, index_type, attributes)
        ok(f"index '{index_key}' ({index_type})")
        time.sleep(0.8)
    except AppwriteException as e:
        if is_already_exists(e):
            skip(f"index '{index_key}'")
        else:
            err(f"index '{index_key}': {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n=== TN StuScholar — Appwrite Setup ===")

    if not all([PROJECT_ID, API_KEY, DB_ID]):
        print("\n✗ ERROR: .env is incomplete. Fill in:")
        print("  APPWRITE_PROJECT_ID, APPWRITE_API_KEY, APPWRITE_DATABASE_ID")
        sys.exit(1)

    print(f"  Endpoint   : {ENDPOINT}")
    print(f"  Project ID : {PROJECT_ID}")
    print(f"  Database ID: {DB_ID}")

    # ── Try to create collections (needs collections.write scope)
    section("Collections")
    ensure_collection(USERS_COL,  "Users")
    ensure_collection(TOKENS_COL, "Tokens")
    ensure_collection(APPS_COL,   "Applications")

    # Wait for Appwrite to be ready before adding attributes
    time.sleep(2)

    # ── users attributes ──────────────────────────────────────────────────────
    section(f"Attributes → '{USERS_COL}'")
    str_attr(USERS_COL, "name",          100, True)
    str_attr(USERS_COL, "email",         255, True)
    str_attr(USERS_COL, "password_hash", 512, True)
    str_attr(USERS_COL, "created_at",    50,  False)
    time.sleep(1.5)
    section(f"Indexes → '{USERS_COL}'")
    ensure_index(USERS_COL, "email_unique", "unique", ["email"])

    # ── tokens attributes ─────────────────────────────────────────────────────
    section(f"Attributes → '{TOKENS_COL}'")
    str_attr(TOKENS_COL, "token",      36,  True)
    str_attr(TOKENS_COL, "email",      255, True)
    str_attr(TOKENS_COL, "created_at", 50,  False)

    # ── applications attributes ───────────────────────────────────────────────
    section(f"Attributes → '{APPS_COL}'")
    str_attr(APPS_COL, "email",          255, True)
    str_attr(APPS_COL, "ref_id",         50,  True)
    str_attr(APPS_COL, "group_id",       50,  False)
    str_attr(APPS_COL, "scheme_id",      100, True)
    str_attr(APPS_COL, "scheme_name",    255, True)
    int_attr(APPS_COL, "benefit_value",  True)
    str_attr(APPS_COL, "status",         50,  False)
    str_attr(APPS_COL, "applied_at",     50,  False)
    str_attr(APPS_COL, "guardian_name",  255, False)
    str_attr(APPS_COL, "college_name",   255, False)
    str_attr(APPS_COL, "account_number", 100, False)
    str_attr(APPS_COL, "ifsc",           20,  False)
    time.sleep(1.5)
    section(f"Indexes → '{APPS_COL}'")
    ensure_index(APPS_COL, "email_idx", "key", ["email"])

    print("\n=== Setup complete! ===")
    print("Run:  python main.py\n")


if __name__ == "__main__":
    main()
