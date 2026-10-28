# Learning Node — DPO delta from verified preference pairs (cycle 3+)
#
# Evidence chain: self-SFT on own successes degrades held-out perf
# (node cycle-1: 30->15, cycle-2: 30->21.7; consistent with SVD 48.9<51.5
# and Tier-0c -1.3%). Remaining principled lever: contrastive training on
# (chosen=verified success, rejected=failure) pairs of the SAME task —
# zero judge cost, both trajectories already collected.
#
# Gate unchanged: +2% held-out margin, pre-registered. If DPO also fails
# the gate, the node-learning mechanism gets a STOP verdict and the
# Learning Node ships with monitor + gate only (both validated).
from __future__ import annotations
import random

import torch
from peft import LoraConfig, get_peft_model

from experiments.run_longhorizon_demo import build_kb, hop_paths, load_model
from src.node.nightly import (NODE_DIR, to_sft_text)


def dpo_pairs(rows):
    """Same-task (chosen_turns, rejected_turns) pairs, serialized."""
    kb, people = build_kb()
    by_id = {t["id"]: t for t in hop_paths(kb, people, n=1000, seed=11)}
    ok = [r for r in rows if r["success"]]
    bad = [r for r in rows if not r["success"]]
    by_task_bad = {}
    for r in bad:
        by_task_bad.setdefault(r["task_id"], []).append(r)
    pairs = []
    for r in ok:
        cands = by_task_bad.get(r["task_id"])
        if not cands:
            continue
        t = by_id[r["task_id"]]
        chosen = to_sft_text(t, r["turns"])          # [(prompt, target), ...]
        rej = to_sft_text(t, cands[0]["turns"])
        if len(chosen) != len(rej):
            continue
        pairs.append((chosen, rej))
    return pairs


def _seq_logprob(model, tok, prompt, target):
    """Sum of target-token logprobs for one (prompt, target)."""
    p_ids = tok(prompt, return_tensors="pt", truncation=True,
                max_length=2048).input_ids
    full = tok(prompt + target, return_tensors="pt", truncation=True,
               max_length=2048).input_ids.to("cuda:0")
    labels = full.clone()
    labels[:, :p_ids.shape[1]] = -100
    out = model(input_ids=full, labels=labels)
    n = int((labels != -100).sum().item())
    return -out.loss.item() * n


def train_delta_dpo(node_id, rows, beta=0.1, n_epochs=1, lr=5e-5, seed=7):
    random.seed(seed)
    pairs = dpo_pairs(rows)
    if len(pairs) < 8:
        print(f"[node:{node_id}] only {len(pairs)} preference pairs — skip")
        return None
    tok, base = load_model()

    # 1) reference logprobs with the pristine base model (frozen, no adapter)
    ref = {}
    with torch.no_grad():
        for i, (chosen, rej) in enumerate(pairs):
            for prompt, target in chosen + rej:
                ref[(i, prompt, target)] = _seq_logprob(base, tok, prompt, target)

    # 2) attach LoRA, train DPO
    cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(base, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    order = list(range(len(pairs)))
    for _ in range(n_epochs):
        random.shuffle(order)
        for i in order:
            chosen, rej = pairs[i]
            pc = sum(_seq_logprob(model, tok, p, t) for p, t in chosen)
            pr = sum(_seq_logprob(model, tok, p, t) for p, t in rej)
            rc = sum(ref[(i, p, t)] for p, t in chosen)
            rr = sum(ref[(i, p, t)] for p, t in rej)
            loss = -torch.nn.functional.logsigmoid(
                torch.tensor(beta * ((pc - rc) - (pr - rr)), device="cuda:0"))
            loss.backward()
            opt.step(); opt.zero_grad()
    d = NODE_DIR / node_id
    ad = d / "delta_dpo"
    model.save_pretrained(str(ad))
    print(f"[node:{node_id}] DPO delta trained on {len(pairs)} preference pairs")
    return ad


if __name__ == "__main__":
    import argparse, json, sys
    sys.path.insert(0, ".")
    from src.node.nightly import collect, gate, sync
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", required=True)
    ap.add_argument("--work", default=None, help="existing work.jsonl (skip collect)")
    ap.add_argument("--gate-n", type=int, default=60)
    a = ap.parse_args()
    if a.work:
        rows = [json.loads(l) for l in open(a.work, encoding="utf-8") if l.strip()]
        print(f"[node:{a.node}] reusing {len(rows)} collected trajectories")
    else:
        rows, _, _ = collect(a.node, 150)
    ad = train_delta_dpo(a.node, rows)
    if ad is not None:
        gate(a.node, ad, a.gate_n)
        sync(a.node)
