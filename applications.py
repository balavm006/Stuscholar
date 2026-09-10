"""
applications.py — Appwrite TablesDB store (SDK v24)
---------------------------------------------------------------
Uses the non-deprecated TablesDB service with list_rows / create_row
instead of the deprecated Databases list_documents / create_document.
"""
from __future__ import annotations

import os
import random
import string
from datetime import datetime, timezone
from typing import Any

from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.query import Query
from appwrite.services.tables_db import TablesDB

from eligibility_engine import load_schemes

# ── Config ────────────────────────────────────────────────────────────────────
APPWRITE_ENDPOINT   = os.getenv("APPWRITE_ENDPOINT",   "https://cloud.appwrite.io/v1")
APPWRITE_PROJECT_ID = os.getenv("APPWRITE_PROJECT_ID", "")
APPWRITE_API_KEY    = os.getenv("APPWRITE_API_KEY",    "")
DATABASE_ID       = os.getenv("APPWRITE_DATABASE_ID",     "")
APPS_COLLECTION   = os.getenv("APPWRITE_APPS_COLLECTION", "applications")

SCHEMES = {s["scheme_id"]: s for s in load_schemes()}


def _db() -> TablesDB:
    client = Client()
    (client
        .set_endpoint(APPWRITE_ENDPOINT)
        .set_project(APPWRITE_PROJECT_ID)
        .set_key(APPWRITE_API_KEY))
    return TablesDB(client)


def _doc_to_dict(doc) -> dict[str, Any]:
    """Convert Appwrite v24 Row/Document → plain dict."""
    if hasattr(doc, 'data') and isinstance(doc.data, dict):
        return dict(doc.data)
    if isinstance(doc, dict):
        return dict(doc)
    try:
        return dict(doc.data)
    except Exception:
        return {}


def create_applications(
    email: str,
    scheme_ids: list[str],
    details: dict[str, str],
) -> list[dict[str, Any]]:
    unknown = [sid for sid in scheme_ids if sid not in SCHEMES]
    if unknown:
        raise ValueError(f"Unknown scheme id(s): {', '.join(unknown)}")
    if not scheme_ids:
        raise ValueError("Select at least one scheme to apply for")

    db       = _db()
    now      = datetime.now(timezone.utc).isoformat(timespec="seconds")
    group_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    created: list[dict[str, Any]] = []

    for sid in scheme_ids:
        scheme = SCHEMES[sid]
        doc = {
            "email":          email,
            "ref_id":         _new_ref(),
            "group_id":       group_id,
            "scheme_id":      sid,
            "scheme_name":    scheme["scheme_name"],
            "benefit_value":  scheme["benefit_value"],
            "status":         "Submitted",
            "applied_at":     now,
            "guardian_name":  details.get("guardian_name",  ""),
            "college_name":   details.get("college_name",   ""),
            "account_number": details.get("account_number", ""),
            "ifsc":           details.get("ifsc",           ""),
        }
        db.create_row(DATABASE_ID, APPS_COLLECTION, ID.unique(), doc)
        created.append({**doc, "details": {
            "guardian_name":  doc["guardian_name"],
            "college_name":   doc["college_name"],
            "account_number": doc["account_number"],
            "ifsc":           doc["ifsc"],
        }})

    return created


def get_applications(email: str) -> list[dict[str, Any]]:
    try:
        result = _db().list_rows(
            DATABASE_ID, APPS_COLLECTION,
            queries=[
                Query.equal("email", email),
                Query.order_desc("applied_at"),
                Query.limit(200),
            ]
        )
        out = []
        for doc in result.rows:
            d = _doc_to_dict(doc)
            out.append({**d, "details": {
                "guardian_name":  d.get("guardian_name",  ""),
                "college_name":   d.get("college_name",   ""),
                "account_number": d.get("account_number", ""),
                "ifsc":           d.get("ifsc",           ""),
            }})
        return out
    except (AppwriteException, AttributeError):
        return []


def _new_ref() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix    = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"REF-{date_part}-{suffix}"