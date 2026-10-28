# M1a: second math domain (SVAMP) — same execution-verified PoT recipe.
# SVAMP: arithmetic word problems, numeric gold answers -> run_one verifier
# works unchanged. Writes work_svamp.jsonl + a domain battery split.
from __future__ import annotations
import json, random, sys

from src.node.pot_node import (
    POT_PROMPT, _extract_code, run_one, extract_last_number,
)
from src.node.teacher import load_teacher


def _load_svamp(n=900, seed=7):
    from datasets import load_dataset
    for name in ("SVAMP", "ChilleD/SVAMP", "arkilpatel/SVAMP"):
        try:
            ds = load_dataset(name)
            break
        except Exception:
            continue
    else:
        raise RuntimeError("no SVAMP dataset found")
    split = ds.get("train") or list(ds.values())[0]
    rows = [{"id": f"svamp-{i}", "question": f"{r['Body']} {r['Question']}",
             "answer": str(r["Answer"]), "domain": "svamp"}
            for i, r in enumerate(split)]
    rng = random.Random(seed)
    rng.shuffle(rows)
    return rows[:n]


def collect_svamp_pot(node_id, target=400, max_problems=900, seed=7,
                      batch=16):
    """Teacher writes one PoT program per SVAMP problem; keep verified."""
    import time
    ndir = sys.modules["src.node.nightly"].NODE_DIR / node_id
    ndir.mkdir(parents=True, exist_ok=True)
    out = ndir / "work_svamp.jsonl"
    pool = _load_svamp(max_problems, seed)
    from src.node.teacher import TEACHER
    ttok, tmodel = load_teacher()
    ttok.padding_side = "left"
    rows, done = [], 0
    if out.exists():  # resume
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        done_ids = {r["id"] for r in rows}
        pool = [p for p in pool if p["id"] not in done_ids]
    print(f"[svamp] pool {len(pool)}, have {len(rows)}/{target}", flush=True)
    for i in range(0, len(pool), batch):
        if len(rows) >= target:
            break
        chunk = pool[i:i + batch]
        prompts = [POT_PROMPT.format(q=p["question"]) for p in chunk]
        ids = ttok(prompts, return_tensors="pt", padding=True,
                   truncation=True, max_length=1024).to("cuda:0")
        o = tmodel.generate(**ids, max_new_tokens=768, do_sample=False,
                            pad_token_id=ttok.pad_token_id or ttok.eos_token_id)
        for j, p in enumerate(chunk):
            text = ttok.decode(o[j][ids["input_ids"].shape[1]:],
                               skip_special_tokens=True)
            code = _extract_code(text)
            if not code:
                continue
            ok, number = run_one(code)
            gold = extract_last_number(p["answer"])
            if ok and number is not None and gold is not None and \
                    abs(number - gold) < 1e-4:
                rows.append({"id": p["id"], "question": p["question"],
                             "answer": p["answer"], "program": code,
                             "teacher": True, "teacher_id": TEACHER,
                             "domain": "svamp"})
        done += len(chunk)
        with out.open("a") as f:
            for r in rows[-len(chunk):]:
                f.write(json.dumps(r) + "\n")
        print(f"[svamp] {done}/{len(pool)} problems, {len(rows)} verified",
              flush=True)
    # battery split: 100 held out for admission, rest training
    if len(rows) >= target:
        rng = random.Random(11)
        rng.shuffle(rows)
        held, train = rows[:100], rows[100:]
        (ndir / "battery_svamp.jsonl").write_text(
            "\n".join(json.dumps(r) for r in held))
        (ndir / "train_svamp.jsonl").write_text(
            "\n".join(json.dumps(r) for r in train))
        print(f"[svamp] DONE {len(train)} train + {len(held)} held out",
              flush=True)
    return len(rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--target", type=int, default=400)
    a = ap.parse_args()
    collect_svamp_pot(a.node, target=a.target)
