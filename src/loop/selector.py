"""Loop-arm data selection: probe the current policy on a pool subset, bucket by
solve rate, and oversample the weak buckets for the next training slice.

This is the minimal viable closed loop: SELECTION-driven (reweighting measured-hard
problems), not synthesis-driven — synthesis is Stage B+ and must be validated against
selection first (cheaper, harder to hack).
"""
from __future__ import annotations
import random
from collections import defaultdict


def bucket_by_difficulty(results: list[dict], buckets: int = 5) -> dict[int, list[str]]:
    """results: [{id, solved: bool}] -> bucket_id -> [ids]. Bucket 0 = hardest."""
    by_id = {r["id"]: r["solved"] for r in results}
    # difficulty proxy when first probing: bucket by solved flag; unsolved are the
    # weak bucket. With repeated cycles we refine using solve-rate estimate.
    out: dict[int, list[str]] = defaultdict(list)
    for pid, solved in by_id.items():
        out[0 if not solved else buckets - 1].append(pid)
    return dict(out)


def select_slice(pool: list[dict], difficulty: dict[int, list[str]] | None,
                 slice_problems: int, strategy: str = "weak_bucket_heavy",
                 rng: random.Random | None = None) -> list[str]:
    """Return ids for the next training slice.

    - weak_bucket_hard: 70% from unsolved bucket, 30% uniform refresh (exploration).
    - uniform: fixed random subset (static-arm behavior).
    """
    rng = rng or random.Random(0)
    ids = [p["id"] for p in pool]
    if strategy == "uniform" or not difficulty:
        return rng.sample(ids, min(slice_problems, len(ids)))

    weak = difficulty.get(0, [])
    rest = [i for i in ids if i not in set(weak)]
    n_weak = min(int(slice_problems * 0.7), len(weak))
    n_rest = slice_problems - n_weak
    chosen = rng.sample(weak, n_weak) if weak else []
    chosen += rng.sample(rest, min(n_rest, len(rest)))
    return chosen


def tokens_of_slice(pool_by_id: dict, slice_ids: list[str], est_tokens_per_problem: int) -> int:
    return len(slice_ids) * est_tokens_per_problem
