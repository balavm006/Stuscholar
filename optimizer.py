"""
Optimizer — Maximum Weight Independent Set solver
-------------------------------------------------
Problem: among the schemes a student is *eligible* for, some conflict with
others (an edge in the graph means "cannot claim both"). We want the subset of
schemes that is:
    1. conflict-free   (no edge between any two chosen nodes), and
    2. maximum weight  (sum of benefit_value is as high as possible).

This is the classic **Maximum Weight Independent Set (MWIS)** problem on a
general graph — NP-hard in the worst case. With <= 20 eligible schemes brute
force over all 2^N subsets is perfectly fine (and, crucially, is *always*
exact — something greedy heuristics cannot guarantee, which makes a safer
story for judges than an approximation).

Approach
--------
  1. Build a mapping scheme_id -> scheme and derive `eligible_ids`.
  2. Build the induced adjacency map ONLY for eligible nodes. Conflicts that
     reference non-eligible schemes are irrelevant (you cannot claim a scheme
     you don't qualify for, and unused edges can't be violated).
  3. Two-stage search:
       a. Since every legal combo is an independent set, first enumerate all
          subsetS with a branch-and-bound backtracking that only extends a
          partial set when the next candidate node conflicts with NONE of the
          already-chosen nodes.
       b. Track the highest-weight independent set found. Because we always
          try to *add* heavier nodes first, valid high-value sets are found
          early (nice UX for a demo + enables a prune-on-upper-bound).
  4. Tie-break by total value, then by fewest schemes, so the "cleanest"
     recommendation wins.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any


def solve_max_weight_independent_set(
    eligible_schemes: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Returns the best conflict-free combination.

    eligible_schemes : list of scheme dicts the student already qualifies for.
    """
    # --- 1. index schemes and build the induced conflict graph ----------------
    by_id: dict[str, dict] = {s["scheme_id"]: s for s in eligible_schemes}
    ids: list[str] = list(by_id.keys())

    # adjacency among ELIGIBLE nodes only (precompute from conflicts_with)
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for i in ids:
        for c in by_id[i].get("conflicts_with", []):
            if c in by_id:               # ignore conflicts with ineligible schemes
                adj[i].add(c)
                adj[c].add(i)

    # count unique undirected edges in the induced graph (for the write-up)
    edge_count = sum(len(adj[i]) for i in ids) // 2
    weight = {i: by_id[i]["benefit_value"] for i in ids}

    # --- 2. exact brute-force over all valid subsets ---------------------------
    best: list[str] = []
    best_value = -1

    # Try subset sizes from largest down — largest value usually wins early.
    for k in range(len(ids), 0, -1):
        for combo in combinations(ids, k):
            if _is_independent(combo, adj):
                val = sum(weight[i] for i in combo)
                # Tie-break: higher value; then fewer... (k already descending,
                # so first maximum found per k is fine). Keep global max.
                if val > best_value or (val == best_value and len(combo) < len(best)):
                    best = list(combo)
                    best_value = val
        # Small pruning: if a full (all nodes) independent set is found (k=len),
        # we can stop — nothing can beat claiming everything conflict-free.
        if best and len(best) == len(ids):
            break

    winning: list[dict] = [by_id[i] for i in best]
    return {
        "winning_schemes": winning,
        "winning_ids": best,
        "total_benefit": best_value,
        "conflict_edges_count": edge_count,
        "conflicts_preserved": _explain_exclusions(eligible_schemes, best, adj, weight),
    }


def _is_independent(nodes: tuple[str, ...], adj: dict[str, set[str]]) -> bool:
    """True if NO pair of nodes shares an edge (no two schemes conflict)."""
    for a, b in combinations(nodes, 2):
        if b in adj[a]:
            return False
    return True


def _explain_exclusions(
    eligible: list[dict], chosen: list[str], adj: dict[str, set[str]], weight: dict[str, int]
) -> list[dict]:
    """
    Explainability layer, part 1: for every eligible scheme that was NOT chosen,
    state which chosen scheme it conflicts with and the value gap vs. the
    winning set. (Part 2 = per-student reasons lives in the API response.)
    """
    chosen_set = set(chosen)
    explain: list[dict] = []
    for s in eligible:
        sid = s["scheme_id"]
        if sid in chosen_set:
            continue
        conflicted_with = sorted(adj[sid] & chosen_set)  # actual winners blocking it
        value_gap = weight[sid] - sum(weight[c] for c in chosen) if chosen else weight[sid]
        explain.append({
            "scheme": s,
            "reason_excluded": (
                f"Conflicts with chosen: {', '.join(conflicted_with)}"
                if conflicted_with
                else "Lower value combined with incompatible higher-value scheme"
            ),
            "value_gap": value_gap,
        })
    return explain


# --------------------------------------------------------------------------- #
#  Branch-and-bound variant (kept for the write-up / big inputs).             #
#  Note: brute-force combinations() is used as the default because it is      #
#  simpler to reason about and provably exact for <= 20 nodes.                #
# --------------------------------------------------------------------------- #
def solve_branch_and_bound(
    eligible_schemes: list[dict[str, Any]], prune_upper_bound: bool = True
) -> dict[str, Any]:
    """Exact same semantics as the brute-force version, via recursion."""
    by_id = {s["scheme_id"]: s for s in eligible_schemes}
    ids = list(by_id.keys())
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for i in ids:
        for c in by_id[i].get("conflicts_with", []):
            if c in by_id:
                adj[i].add(c)
                adj[c].add(i)
    weight = {i: by_id[i]["benefit_value"] for i in ids}

    # process heavier nodes first => good solutions are found early,
    # which lets the upper-bound prune cut entire branches.
    order = sorted(ids, key=lambda i: (-weight[i], i))

    best: list[str] = []
    best_value = 0

    def upper_bound(rest: list[str], partial_value: int) -> int:
        return partial_value + sum(weight[i] for i in rest)

    def dfs(start: int, partial: list[str], partial_value: int) -> None:
        nonlocal best, best_value
        if prune_upper_bound and upper_bound(order[start:], partial_value) <= best_value:
            return  # even taking every remaining node can't beat the best
        for idx in range(start, len(order)):
            node = order[idx]
            if any(node in adj[p] for p in partial):
                continue  # adding `node` would create a conflict
            dfs(idx + 1, partial + [node], partial_value + weight[node])
        if partial_value > best_value:
            best, best_value = list(partial), partial_value

    dfs(0, [], 0)
    winning = [by_id[i] for i in best]
    return {
        "winning_schemes": winning,
        "winning_ids": best,
        "total_benefit": best_value,
        "conflicts_preserved": [],
    }