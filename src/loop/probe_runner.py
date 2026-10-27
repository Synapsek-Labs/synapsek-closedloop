"""Run the probe battery or a pool subset against the current policy, score it."""
from __future__ import annotations
from src.cartography.battery import is_correct
from src.loop.train_arm import probe


def run_battery(model, tok, problems: list[dict], max_new: int = 512) -> list[dict]:
    """problems: [{id, question, answer}] -> [{id, solved, question}]"""
    raw = probe(model, tok, [{"id": p["id"], "question": p["question"]} for p in problems],
                max_new=max_new)
    gold = {p["id"]: p["answer"] for p in problems}
    return [{"id": r["id"], "question": r["question"], "solved": is_correct(r["text"], gold[r["id"]])}
            for r in raw]


def solve_rate(results: list[dict]) -> float:
    return sum(r["solved"] for r in results) / max(1, len(results))
