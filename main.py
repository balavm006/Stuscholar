"""
FastAPI backend — AI Scholarship & Scheme Eligibility Matcher
-------------------------------------------------------------
Endpoints:
  GET  /api                    -> API info
  GET  /schemes                -> all scheme definitions (the data model)
  GET  /sample-profiles        -> demo profiles for one-click testing
  POST /match                  -> core pipeline: eligibility + MWIS optimizer +
                                  explainability + near-miss gaps
  POST /register               -> create account (returns bearer token)
  POST /login                  -> sign in (returns bearer token)
  POST /logout                 -> invalidate token
  GET  /me                     -> current user (Bearer token)
  POST /applications           -> apply for recommended schemes (Bearer token)
  GET  /applications           -> my applications dashboard (Bearer token)

Run with:
    uvicorn main:app --reload
"""
from __future__ import annotations

# Load .env file before anything else (Appwrite credentials etc.)
from dotenv import load_dotenv
load_dotenv()

from typing import Any



from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

import auth
import applications
from eligibility_engine import find_eligible, load_schemes, near_miss
from optimizer import solve_max_weight_independent_set

app = FastAPI(title="AI Scholarship Matcher — Tamil Nadu")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCHEMES = load_schemes()


class StudentProfile(BaseModel):
    income: int
    community: str
    gender: str
    disability_pct: float = 0
    course_type: str
    age: int = 19
    # declarative boolean conditions evaluated against scheme rules
    first_graduate: bool = False
    min_score_50: bool = False
    merit_top_20: bool = False
    govt_seat: bool = False
    hostel: bool = False
    rural: bool = False


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class ApplicationIn(BaseModel):
    scheme_ids: list[str]
    guardian_name: str = ""
    college_name: str = ""
    account_number: str = ""
    ifsc: str = ""


def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """FastAPI dependency: resolves the Bearer token to a user dict."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Sign in required")
    token = authorization.removeprefix("Bearer ").strip()
    user = auth.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


@app.get("/api")
def root() -> dict:
    return {
        "name": "AI Scholarship & Scheme Eligibility Matcher (Tamil Nadu)",
        "endpoints": {
            "schemes": "/schemes",
            "match": "POST /match",
        },
    }


@app.get("/schemes")
def all_schemes() -> dict:
    return {"count": len(SCHEMES), "schemes": SCHEMES}


# --------------------------------------------------------------------------- #
# Auth                                                                        #
# --------------------------------------------------------------------------- #
@app.post("/register")
def register(body: RegisterIn) -> dict:
    try:
        user = auth.register(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token, user = auth.login(body.email, body.password)
    return {"token": token, "user": user}


@app.post("/login")
def login(body: LoginIn) -> dict:
    try:
        token, user = auth.login(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": token, "user": user}


@app.post("/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if authorization:
        auth.logout(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@app.get("/me")
def me(user: dict[str, Any] = Depends(require_user)) -> dict:
    applications_count = len(applications.get_applications(user["email"]))
    return {"user": user, "applications_count": applications_count}


# --------------------------------------------------------------------------- #
# Applications                                                                #
# --------------------------------------------------------------------------- #
@app.post("/applications")
def apply(body: ApplicationIn, user: dict[str, Any] = Depends(require_user)) -> dict:
    try:
        created = applications.create_applications(
            user["email"], body.scheme_ids, body.model_dump()
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    total = sum(a["benefit_value"] for a in created)
    return {"applications": created, "count": len(created), "total_benefit": total}


@app.get("/applications")
def my_applications(user: dict[str, Any] = Depends(require_user)) -> dict:
    apps = applications.get_applications(user["email"])
    return {"count": len(apps), "applications": list(reversed(apps))}


@app.post("/match")
def match(profile: StudentProfile, user: dict[str, Any] = Depends(require_user)) -> dict:
    p = profile.model_dump()

    # ---- Step 1: eligibility -----------------------------------------------
    verdicts = find_eligible(p)                     # every scheme + reasons
    eligible = [r for r in verdicts if r.eligible]

    # ---- Step 2: MWIS optimization over the eligible set --------------------
    opt = solve_max_weight_independent_set([r.scheme for r in eligible])

    winning_ids = set(opt["winning_ids"])

    # ---- Step 3: explainability --------------------------------------------
    winning_detail = {
        r.scheme["scheme_id"]: {
            "scheme": r.scheme,
            "why": r.reasons,
        }
        for r in eligible if r.scheme["scheme_id"] in winning_ids
    }

    excluded = []
    for s in opt["conflicts_preserved"]:
        sid = s["scheme"]["scheme_id"]
        j = next((v for v in eligible if v.scheme["scheme_id"] == sid), None)
        excluded.append({
            "scheme": s["scheme"],
            "why_eligible": j.reasons if j else [],
            "reason_excluded": s["reason_excluded"],
            "value_gap_vs_winning": s["value_gap"],
        })

    # ---- Step 4: near-miss / gap-to-eligibility ----------------------------
    gaps = []
    for r in near_miss(p):
        gaps.append({
            "scheme": r.scheme,
            "missing": r.missing,
            "value_missed": r.scheme["benefit_value"],
        })

    return {
        "profile_matched": p,
        "summary": {
            "schemes_checked": len(SCHEMES),
            "eligible_count": len(eligible),
            "recommended_count": len(opt["winning_ids"]),
            "total_benefit": opt["total_benefit"],
            "conflict_edges_considered": opt.get("conflict_edges_count", 0),
        },
        "recommended": {
            "schemes_detail": list(winning_detail.values()),
            "total_benefit": opt["total_benefit"],
            "algorithm": "Maximum Weight Independent Set (exact brute force over "
                          f"{len(eligible)} eligible nodes / 2^{len(eligible)} subsets)",
        },
        "excluded_eligible": excluded,
        "near_miss_gaps": gaps,
    }


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)