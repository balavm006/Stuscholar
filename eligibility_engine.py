"""
Eligibility Engine
-----------------
Rules-as-data: every scheme in schemes.json declares its own eligibility
criteria. This module simply *evaluates* those declared rules against a
student profile — no hardcoded if/else chains for individual schemes.

Adding a new scheme = adding one JSON object + optional conflict edges.
No code changes required.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMES_PATH = Path(__file__).resolve().parent / "schemes.json"


class MatchResult:
    """A single eligibility verdict for one scheme."""

    __slots__ = ("scheme", "eligible", "reasons", "missing")

    def __init__(self, scheme: dict, eligible: bool, reasons: list[str], missing: list[str]):
        self.scheme = scheme
        self.eligible = eligible
        self.reasons = reasons      # human-readable "why you matched"
        self.missing = missing      # human-readable "what blocked you" (near-miss)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme": self.scheme,
            "eligible": self.eligible,
            "reasons": self.reasons,
            "missing": self.missing,
        }


def load_schemes(path: Path = SCHEMES_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["schemes"]


def check_scheme(profile: dict, scheme: dict) -> MatchResult:
    """
    Evaluate ONE scheme against the student profile.

    Each rule produces either:
      - a positive reason (a check the student PASSED), or
      - a blocking reason (a check the student FAILED).

    If all *blocking* rules pass, the student is eligible.
    """
    el = scheme["eligibility"]
    reasons: list[str] = []
    missing: list[str] = []

    income = profile.get("income", 0)
    max_income = el.get("max_income")
    if max_income is not None:
        if income <= max_income:
            reasons.append(f"Annual income ₹{income:,} is within the ₹{max_income:,} ceiling")
        else:
            missing.append(
                f"Annual income ₹{income:,} exceeds the ₹{max_income:,} ceiling by ₹{income - max_income:,}"
            )

    communities = el.get("communities", [])
    if communities:
        comm = profile.get("community", "")
        if comm in communities:
            reasons.append(f"Community ({comm}) is covered by this scheme")
        else:
            missing.append(f"Community ({comm}) is not among {', '.join(communities).upper()}")

    genders = el.get("genders", [])
    if genders:
        gender = profile.get("gender", "")
        if gender in genders:
            reasons.append(f"Gender ({gender}) is covered by this scheme")
        else:
            missing.append(f"Gender ({gender}) is not covered (requires: {', '.join(genders)})")

    min_dis = el.get("min_disability_pct", 0)
    if min_disability := el.get("min_disability_pct", 0):
        pct = profile.get("disability_pct", 0)
        if pct >= min_disability:
            reasons.append(f"Disability {pct}% meets the minimum {min_disability}% requirement")
        else:
            missing.append(f"Disability {pct}% is below the required minimum of {min_disability}%")

    course_types = el.get("course_types", [])
    if course_types:
        course = profile.get("course_type", "")
        if course in course_types:
            reasons.append(f"Course type ({course}) is covered by this scheme")
        else:
            missing.append(f"Course type ({course}) is not covered (requires: {', '.join(course_types)})")

    # Age gate (declarative): age_min/age_max on the scheme, age on the profile
    age = profile.get("age", 0)
    age_min = el.get("age_min", 0)
    age_max = el.get("age_max", 999)
    if age_min > 0 or age_max < 999:
        if age_min <= age <= age_max:
            reasons.append(f"Age {age} is within the {age_min}–{age_max} window")
        else:
            missing.append(f"Age {age} is outside the required {age_min}–{age_max} window")

    # Named boolean conditions (declarative rules-as-data):
    # each entry is {key, label}; the profile supplies a matching boolean.
    for cond in el.get("conditions", []):
        if bool(profile.get(cond["key"], False)):
            reasons.append(cond["label"])
        else:
            missing.append(f"Condition not met: {cond['label']}")

    eligible = len(missing) == 0
    return MatchResult(scheme, eligible, reasons, missing)


def find_eligible(profile: dict) -> list[MatchResult]:
    """Evaluate every scheme and return the full verdict list (eligible + near-miss)."""
    return [check_scheme(profile, s) for s in load_schemes()]


def eligible_only(profile: dict) -> list[MatchResult]:
    return [r for r in find_eligible(profile) if r.eligible]


def near_miss(profile: dict, gap_income: int = 20000) -> list[MatchResult]:
    """
    Near-miss detection: a student who fails ONLY income by a small margin
    (> 0 but <= gap_income over the ceiling) is returned so the app can show
    them what they are blocked from and its value.
    """
    out = []
    for r in find_eligible(profile):
        if r.eligible or len(r.missing) != 1:
            continue
        if "ceiling" not in r.missing[0].lower() and "exceeds" not in r.missing[0].lower():
            continue
        income = profile.get("income", 0)
        max_income = r.scheme["eligibility"].get("max_income", 0)
        over = income - max_income
        if 0 < over <= gap_income:
            out.append(r)
    return out


if __name__ == "__main__":
    demo = {
        "income": 265000,
        "community": "bc",
        "gender": "female",
        "disability_pct": 0,
        "course_type": "undergraduate",
        "first_graduate": True,
    }
    for r in near_miss(demo):
        print(r.scheme["scheme_id"], r.missing)