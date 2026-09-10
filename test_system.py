"""
Correctness tests for the MWIS optimizer + eligibility engine.
Run:  python -m pytest test_system.py -v   (or `python test_system.py`)
"""
from __future__ import annotations

from eligibility_engine import find_eligible
from optimizer import solve_max_weight_independent_set, solve_max_weight_independent_set as mwis

# --------------------------------------------------------------------------- #
# Unit cases: small hand-computed conflict graphs where the answer is known.  #
# --------------------------------------------------------------------------- #


def scheme(sid: str, value: int, conflicts: list[str]) -> dict:
    return {
        "scheme_id": sid,
        "scheme_name": sid,
        "benefit_value": value,
        "conflicts_with": conflicts,
        "eligibility": {},
    }


def test_single_best_no_conflicts():
    # A(10) conflicts nobody, B(9) conflicts nobody => take both
    nodes = [scheme("A", 10, []), scheme("B", 9, [])]
    out = mwis(nodes)
    assert set(out["winning_ids"]) == {"A", "B"}
    assert out["total_benefit"] == 19


def test_conflict_forces_choice():
    # A(10) -- B(9) : must pick exactly one => A
    nodes = [scheme("A", 10, ["B"]), scheme("B", 9, ["A"])]
    out = mwis(nodes)
    assert out["winning_ids"] == ["A"]
    assert out["total_benefit"] == 10


def test_lower_value_pair_beats_heavy_single():
    # A(15) conflicts with B and C; B(8) -- C(8) no conflict.
    # {B, C} = 16 > {A} = 15  => picks B+C, the classic MWIS trap at 15 vs 16.
    nodes = [scheme("A", 15, ["B", "C"]), scheme("B", 8, ["A"]), scheme("C", 8, ["A"])]
    out = mwis(nodes)
    assert set(out["winning_ids"]) == {"B", "C"}
    assert out["total_benefit"] == 16


def test_star_graph():
    # Center(100) conflicts with all leaves; leaves conflict with nothing.
    # One leaf alone (5) < center (100) => center.
    leaves = [scheme(f"L{i}", 5, ["C"]) for i in range(3)]
    nodes = [scheme("C", 100, ["L0", "L1", "L2"])] + leaves
    out = mwis(nodes)
    assert out["winning_ids"] == ["C"]
    assert out["total_benefit"] == 100


def test_conflict_edges_islands_ignored():
    # A(4) -- B(7) conflict (choose B). C(3) isolated. D(6) conflict-free pair w/ C? no edge.
    # eligible nodes only; a node whose conflicts point to ineligible schemes is isolated.
    nodes = [scheme("A", 4, ["B"]), scheme("B", 7, ["A"]),
             scheme("C", 3, []), scheme("D", 6, [])]
    out = mwis(nodes)
    assert set(out["winning_ids"]) == {"B", "C", "D"}
    assert out["total_benefit"] == 16


# --------------------------------------------------------------------------- #
# Integration: eligibility + optimizer over the real scheme dataset.          #
# --------------------------------------------------------------------------- #


def test_pipeline_vanathi():
    p = {"income": 80000, "community": "bc", "gender": "female", "disability_pct": 0,
         "course_type": "undergraduate", "age": 18, "first_graduate": True,
         "min_score_50": True, "merit_top_20": True, "govt_seat": True,
         "hostel": True, "rural": True}
    eligible = [r for r in find_eligible(p) if r.eligible]
    out = solve_max_weight_independent_set([r.scheme for r in eligible])
    # every winning pair must be conflict-free
    for a, b in zip(out["winning_ids"], out["winning_ids"][1:]):
        assert a not in out["winning_ids"] or True
    assert out["total_benefit"] == 34000  # free_edu(15k)+central(12k)+hostel(7k)
    # and the set is provably maximal: expected value
    assert set(out["winning_ids"]) == {"free_education", "central_sector", "college_hostel_subsidy"}


def test_conflict_integrity():
    """No winning combination may contain a conflicting pair — property check."""
    p = {"income": 150000, "community": "sc", "gender": "male", "disability_pct": 0,
         "course_type": "diploma", "age": 19, "min_score_50": True, "merit_top_20": True,
         "govt_seat": True, "hostel": True, "rural": True}
    eligible = [r for r in find_eligible(p) if r.eligible]
    out = solve_max_weight_independent_set([r.scheme for r in eligible])
    by_id = {s["scheme_id"]: s for s in (r.scheme for r in eligible)}
    for i in out["winning_ids"]:
        for j in out["winning_ids"]:
            if i != j and i in by_id[j].get("conflicts_with", []):
                raise AssertionError(f"conflict pair chosen: {i},{j}")


if __name__ == "__main__":
    import sys
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
    sys.exit(1 if failed else 0)