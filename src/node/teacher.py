# Teacher-gated distillation — the unexplored branch (Bet C kill-test)
#
# All node-learning negatives share one confound: student = data source.
# This A/B changes ONLY the data source: Qwen2.5-7B-Instruct (teacher,
# 4-bit on the same GPU) generates trajectories on the same workload with
# the same exemplar; the student (Qwen2.5-1.5B) trains with the EXACT
# recipe of the failed self-SFT cycle (1 epoch, lr 5e-5, verified
# successes only). Gate unchanged: +2% held-out margin.
#
# Pre-registered: GO if gate accepts teacher-data delta; if rejected,
# escalate teacher to 32B (RunPod burst ~$5) before any STOP.
from __future__ import annotations
import json
from pathlib import Path

from experiments.run_longhorizon_demo import (build_kb, run_agent, load_model,
                                              MODEL)
from src.node.nightly import (NODE_DIR, make_workload, set_exemplar,
                              to_sft_text, train_delta, gate)

TEACHER = "Qwen/Qwen2.5-7B-Instruct"


def load_teacher():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from transformers import BitsAndBytesConfig
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                           bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(TEACHER)
    m = AutoModelForCausalLM.from_pretrained(TEACHER, quantization_config=q,
                                             dtype=torch.bfloat16,
                                             device_map="cuda:0")
    m.eval()
    return tok, m


def collect_teacher(node_id, n_tasks=100, seed=7):
    kb, people = build_kb()
    set_exemplar(kb)
    tasks = make_workload(kb, people, n_tasks, seed=seed)
    tok, model = load_teacher()
    rows = []
    for i, t in enumerate(tasks):
        r = run_agent(model, tok, t, kb, temperature=0.0)
        r.update({"task_id": t["id"], "hops": [h for h, _ in t["hops"]],
                  "answer": t["answer"], "n_hops": t["n_hops"],
                  "teacher": TEACHER})
        rows.append(r)
    d = NODE_DIR / node_id
    d.mkdir(parents=True, exist_ok=True)
    f = d / "work_teacher.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    ns = sum(x["success"] for x in rows)
    print(f"[teacher] {len(rows)} tasks, {ns} verified successes "
          f"({ns/len(rows):.0%} solve)", flush=True)
    return rows


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, ".")
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--tasks", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    kb, people = build_kb()  # noqa: F841 (exemplar set inside collect_teacher)
    rows = collect_teacher(a.node, a.tasks, a.seed)
    # identical recipe to the rejected self-SFT cycle-4
    ad = train_delta(a.node, rows, seed=a.seed)
    if ad is None:
        print("[teacher] too few verified successes -> stopping")
        sys.exit(0)
    print(f"[teacher] student delta trained on teacher data -> {ad}")
    print("[teacher] run gate in a FRESH process (ops rule)")
