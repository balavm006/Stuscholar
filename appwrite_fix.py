"""
appwrite_fix.py — Auto-detect collections, add all attributes, fix .env
-----------------------------------------------------------------------
Run:  python appwrite_fix.py

This script:
  1. Lists all collections in your Appwrite database
  2. Matches them by name to users / tokens / applications
  3. Creates missing attributes on each collection
  4. Rewrites .env with the correct collection IDs
"""
import warnings; warnings.filterwarnings("ignore", category=DeprecationWarning)

import os, sys, time, re
from dotenv import load_dotenv; load_dotenv()

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.services.databases import Databases

ENDPOINT   = os.getenv("APPWRITE_ENDPOINT",   "https://cloud.appwrite.io/v1")
PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID", "")
API_KEY    = os.getenv("APPWRITE_API_KEY",    "")
DB_ID      = os.getenv("APPWRITE_DATABASE_ID", "")

client = Client()
client.set_endpoint(ENDPOINT).set_project(PROJECT_ID).set_key(API_KEY)
db = Databases(client)

def ok(m):    print(f"  ✓ {m}")
def skip(m):  print(f"  ► {m} (exists)")
def err(m):   print(f"  ✗ {m}")
def sec(m):   print(f"\n--- {m} ---")

def exists_err(e): return "already exists" in str(e).lower() or "409" in str(e)

def str_attr(col_id, key, size, required):
    try:
        db.create_string_attribute(DB_ID, col_id, key, size, required)
        ok(f"{key} (String {size})")
        time.sleep(0.6)
    except AppwriteException as e:
        if exists_err(e): skip(key)
        else: err(f"{key}: {e}")

def int_attr(col_id, key, required):
    try:
        db.create_integer_attribute(DB_ID, col_id, key, required)
        ok(f"{key} (Integer)")
        time.sleep(0.6)
    except AppwriteException as e:
        if exists_err(e): skip(key)
        else: err(f"{key}: {e}")

def ensure_index(col_id, idx_key, idx_type, attrs):
    try:
        db.create_index(DB_ID, col_id, idx_key, idx_type, attrs)
        ok(f"index {idx_key}")
        time.sleep(0.8)
    except AppwriteException as e:
        if exists_err(e): skip(f"index {idx_key}")
        else: err(f"index {idx_key}: {e}")

def main():
    print("\n=== TN StuScholar — Appwrite Fix ===")
    if not all([PROJECT_ID, API_KEY, DB_ID]):
        print("ERROR: .env missing APPWRITE_PROJECT_ID / API_KEY / DATABASE_ID"); sys.exit(1)

    # ── List actual collections ───────────────────────────────────────────────
    sec("Listing your Appwrite collections")
    cols = db.list_collections(DB_ID)
    print(f"Found {cols.total} collection(s):")
    col_map = {}
    for c in cols.collections:
        print(f"  {c.id}  →  {c.name}")
        col_map[c.name.lower()] = c.id   # name.lower() → actual UUID

    # ── Match by name ─────────────────────────────────────────────────────────
    MAPPING = {
        "users":        ("users",        col_map),
        "tokens":       ("tokens",       col_map),
        "applications": ("applications", col_map),
    }
    resolved = {}
    for key, (name, m) in MAPPING.items():
        # Try exact name match first, then partial
        cid = m.get(name) or m.get(name + "s") or None
        if not cid:
            # Fuzzy: find first collection whose name contains the key word
            for cname, cid2 in m.items():
                if key in cname:
                    cid = cid2; break
        if cid:
            resolved[key] = cid
            print(f"  Matched '{key}' → {cid}")
        else:
            print(f"  WARNING: No collection matched '{key}' — will use env value")
            resolved[key] = os.getenv(f"APPWRITE_{key.upper()}_COLLECTION", key)

    USERS_COL  = resolved["users"]
    TOKENS_COL = resolved["tokens"]
    APPS_COL   = resolved["applications"]

    # ── Users attributes ──────────────────────────────────────────────────────
    sec(f"Users collection ({USERS_COL})")
    str_attr(USERS_COL, "name",          100, True)
    str_attr(USERS_COL, "email",         255, True)
    str_attr(USERS_COL, "password_hash", 512, True)
    str_attr(USERS_COL, "created_at",    50,  False)
    time.sleep(1.5)
    ensure_index(USERS_COL, "email_unique", "unique", ["email"])

    # ── Tokens attributes ─────────────────────────────────────────────────────
    sec(f"Tokens collection ({TOKENS_COL})")
    str_attr(TOKENS_COL, "token",      36,  True)
    str_attr(TOKENS_COL, "email",      255, True)
    str_attr(TOKENS_COL, "created_at", 50,  False)

    # ── Applications attributes ───────────────────────────────────────────────
    sec(f"Applications collection ({APPS_COL})")
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
    ensure_index(APPS_COL, "email_idx", "key", ["email"])

    # ── Auto-update .env with correct collection IDs ──────────────────────────
    sec("Updating .env with correct collection IDs")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = re.sub(r"APPWRITE_USERS_COLLECTION=.*",
                         f"APPWRITE_USERS_COLLECTION={USERS_COL}", content)
        content = re.sub(r"APPWRITE_TOKENS_COLLECTION=.*",
                         f"APPWRITE_TOKENS_COLLECTION={TOKENS_COL}", content)
        content = re.sub(r"APPWRITE_APPS_COLLECTION=.*",
                         f"APPWRITE_APPS_COLLECTION={APPS_COL}", content)

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)
        ok(f"APPWRITE_USERS_COLLECTION  = {USERS_COL}")
        ok(f"APPWRITE_TOKENS_COLLECTION = {TOKENS_COL}")
        ok(f"APPWRITE_APPS_COLLECTION   = {APPS_COL}")
    except Exception as e:
        err(f"Could not update .env: {e}")

    print("\n=== Done! Now run:  python main.py ===\n")

if __name__ == "__main__":
    main()
