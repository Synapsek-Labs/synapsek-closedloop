# M1c: MATH-easy domain — competition math, numeric answers only.
# Failure-band target: base expected ~45-60% (per the SVAMP lesson).
import json, random, re, sys

from src.node.pot_node import POT_PROMPT, _extract_code, run_one, extract_last_number
from src.node.teacher import load_teacher, TEACHER

# Static hang filter — pitfall from HANDOFF §3: a CPU-bound infinite loop in
# generated code leaks a GIL-hogging daemon thread in run_one (thread cannot be
# killed) and wedges the collection run silently.
import re as _re

_HANG_RE = _re.compile(r"input\(|while\s+True|time\.sleep|sleep\(", _re.IGNORECASE)


def _safe_run_one(code):
    if _HANG_RE.search(code):
        return False, None
    return run_one(code)


def _numeric(s):
    """Gold is usable only if a float can be extracted from \\boxed{...}."""
    m = re.findall(r"\\boxed\{([^}]+)\}", str(s))
    if not m:
        m = [str(s)]
    return extract_last_number(m[-1]) is not None


def _load_math_easy(n=1200, seed=7):
    from datasets import load_dataset
    ds = None
    for name in ("DigitalLearningGmbH/MATH-lighteval", "EleutherAI/hendrycks_math",
                 "hendrycks/competition_math"):
        try:
            ds = load_dataset(name, "algebra")
            break
        except Exception:
            continue
    if ds is None:
        raise RuntimeError("no MATH dataset found")
    split = ds.get("train") or list(ds.values())[0]
    rows = []
    for i, r in enumerate(split):
        q = r.get("problem") or r.get("question")
        a = r.get("solution") or r.get("answer")
        gold = re.findall(r"\\boxed\{([^}]+)\}", str(a))
        if not gold:
            continue
        gold_num = extract_last_number(gold[-1])
        if gold_num is None:
            continue  # symbolic answers out of scope (execution-verified only)
        if r.get("level") and "Level 5" in str(r["level"]):
            continue  # keep easy/medium band
        rows.append({"id": f"math-{i}", "question": q,
                     "answer": str(gold_num), "domain": "math"})
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:n]


def collect_math_pot(node_id, target=400, max_problems=1200, seed=7, batch=16):
    import time
    ndir = sys.modules["src.node.nightly"].NODE_DIR / node_id
    ndir.mkdir(parents=True, exist_ok=True)
    out = ndir / "work_math.jsonl"
    pool = _load_math_easy(max_problems, seed)
    ttok, tmodel = load_teacher()
    ttok.padding_side = "left"
    rows = []
    if out.exists():
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        done_ids = {r["id"] for r in rows}
        pool = [p for p in pool if p["id"] not in done_ids]
    print(f"[math] pool {len(pool)}, have {len(rows)}/{target}", flush=True)
    for i in range(0, len(pool), batch):
        if len(rows) >= target:
            break
        chunk = pool[i:i + batch]
        prompts = [POT_PROMPT.format(q=p["question"]) for p in chunk]
        ids = ttok(prompts, return_tensors="pt", padding=True,
                   truncation=True, max_length=1024).to("cuda:0")
        o = tmodel.generate(**ids, max_new_tokens=1024, do_sample=False,
                            pad_token_id=ttok.pad_token_id or ttok.eos_token_id)
        new = 0
        for j, p in enumerate(chunk):
            text = ttok.decode(o[j][ids["input_ids"].shape[1]:],
                               skip_special_tokens=True)
            code = _extract_code(text)
            if not code:
                continue
            ok, number = _safe_run_one(code)
            gold = extract_last_number(p["answer"])
            if ok and number is not None and gold is not None and \
                    abs(number - gold) < 1e-4:
                rows.append({"id": p["id"], "question": p["question"],
                             "answer": p["answer"], "program": code,
                             "teacher": True, "teacher_id": TEACHER,
                             "domain": "math"})
                new += 1
        with out.open("a") as f:
            for r in rows[-new:] if new else []:
                f.write(json.dumps(r) + "\n")
        print(f"[math] {min(i+batch,len(pool))}/{len(pool)} problems, "
              f"{len(rows)} verified", flush=True)
    if len(rows) >= target:
        rng = random.Random(11)
        rng.shuffle(rows)
        held, train = rows[:100], rows[100:]
        (ndir / "battery_math.jsonl").write_text(
            "\n".join(json.dumps(r) for r in held))
        (ndir / "train_math.jsonl").write_text(
            "\n".join(json.dumps(r) for r in train))
        print(f"[math] DONE {len(train)} train + {len(held)} held out",
              flush=True)
    return len(rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--target", type=int, default=400)
    a = ap.parse_args()
    collect_math_pot(a.node, target=a.target)
