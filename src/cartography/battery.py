"""Probe battery: build, freeze, load, and evaluate.

The held-out battery is generated ONCE, hashed, and never trained on (tier0_plan.md
honesty rule). The training pool carries per-problem metadata so the loop can bucket
by measured difficulty.
"""
from __future__ import annotations
import hashlib, json, random
from pathlib import Path

GSM8K = "openai/gsm8k"
ANSWER_DIVIDERS = ("####", "=", "answer is", "Answer:")


def extract_last_number(text: str) -> float | None:
    """Last number in the text (handles commas, $, %)."""
    import re
    nums = re.findall(r"-?\$?\d[\d,]*\.?\d*", text)
    if not nums:
        return None
    return float(nums[-1].replace("$", "").replace(",", ""))


def is_correct(generated: str, gold: str) -> bool:
    pred = extract_last_number(generated)
    goldv = extract_last_number(gold)
    if pred is None or goldv is None:
        return False
    return abs(pred - goldv) < 1e-4


def _problem_hash(q: str) -> str:
    return hashlib.sha256(q.encode()).hexdigest()[:16]


def build(probe_out: str = "probes/battery_held_out.jsonl",
          pool_out: str = "probes/pool_train.jsonl",
          n_held_out: int = 400,
          n_pool: int = 5000,
          seed: int = 0):
    """Split GSM8K: held-out battery (frozen) + training pool. Writes JSONL + hashes."""
    from datasets import load_dataset
    ds = load_dataset(GSM8K, "main")
    train = list(ds["train"])
    test = list(ds["test"])
    rng = random.Random(seed)

    battery = test  # test split is NEVER in the training pool by construction
    rng.shuffle(battery)
    held = battery[:n_held_out]
    rng.shuffle(train)
    pool = train[:n_pool]

    Path(probe_out).write_text("\n".join(json.dumps({
        "id": _problem_hash(r["question"]), "question": r["question"],
        "answer": r["answer"].split("####")[-1].strip()}) for r in held) + "\n")

    Path(pool_out).write_text("\n".join(json.dumps({
        "id": _problem_hash(r["question"]), "question": r["question"],
        "answer": r["answer"].split("####")[-1].strip(),
        "used_in_slice": []}) for r in pool) + "\n")

    manifest = {
        "held_out_sha256": hashlib.sha256(Path(probe_out).read_bytes()).hexdigest(),
        "pool_sha256": hashlib.sha256(Path(pool_out).read_bytes()).hexdigest(),
        "n_held_out": len(held), "n_pool": len(pool), "seed": seed,
        "note": "held-out battery generated from GSM8K test split before any training; frozen.",
    }
    Path(probe_out).with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def load(path: str) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def verify_frozen(probe_path: str) -> str:
    """Return the battery hash; caller compares against the manifest to prove no drift."""
    return hashlib.sha256(Path(probe_path).read_bytes()).hexdigest()
