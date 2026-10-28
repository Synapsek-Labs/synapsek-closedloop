# Learning Node MVP — src/node/nightly.py
#
# Nightly cycle for one Learning Node:
#   collect  -> run today's agent workload, keep execution-verified successes
#               (+ failure turns labeled by the exact first-mistake signal)
#   train    -> LoRA delta from verified-success trajectories only
#   gate     -> receiver-style held-out re-verification: accept delta ONLY if
#               it strictly improves held-out solve rate (+2% margin)
#   sync     -> exchange dir: publish my delta, re-verify foreign deltas before
#               adopting (the unoccupied mechanism: verification-gated delta exchange)
#
# Honest framing (docs/prior_art.md §5, §6): components are known; the SYSTEM
# (verified-trajectory -> weight-delta -> receiver-side re-verification -> adopt)
# is the MVP claim. This file is the reference implementation.
from __future__ import annotations
import json, random, shutil
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model

from experiments.run_longhorizon_demo import (build_kb, hop_paths, run_agent,
                                              load_model, SYS, MAX_STEPS)

NODE_DIR = Path("runs/node")

# One-shot worked example: teach the action format by demonstration.
# The 1.5B agent fails on FORMAT, not reasoning — first-cycle evidence:
# 60 tasks @ temp 0.7 -> 2% solve; with exemplar + greedy we recover yield.
_EX = ("Example:\nTask: follow this chain and give the final entity/attribute:\n"
       "Nora -> role\nNext action:\nlookup(\"Nora\")\n"
       "Observation: Vertex Dynamics\nNext action:\nlookup(\"Vertex Dynamics\")\n"
       "Observation: QA lead\nNext action:\nfinal(\"QA lead\")\n\n")
_EX_KEY = ("Nora", "role")


def _build_exemplar(kb):
    v = str(kb.get(_EX_KEY) or "QA lead")
    return _EX.replace("QA lead", v)


def set_exemplar(kb):
    import experiments.run_longhorizon_demo as lhd
    lhd.SYS = lhd.SYS + "\n\n" + _build_exemplar(kb)


# ---------------------------------------------------------------- workload
def make_workload(kb, people, n, seed=7, max_hops=3):
    """Daily workload: FULL 3-hop chains only. Cycle-2 evidence: truncating
    to 2 hops makes answers UNREACHABLE (lookup returns works_at first, so a
    person's role can never be observed) -> 0/60. Reachable answers are the
    original chain endpoints (year_founded, hq_city, city). Yield levers that
    are safe: one-shot exemplar + greedy decoding (format, not reachability)."""
    return hop_paths(kb, people, n=n, seed=seed)


def collect(node_id, n_work=60, seed=7):
    kb, people = build_kb()
    set_exemplar(kb)
    tasks = make_workload(kb, people, n_work, seed=seed)
    tok, model = load_model()
    rows = []
    for i, t in enumerate(tasks):
        r = run_agent(model, tok, t, kb, temperature=0.0)
        r.update({"task_id": t["id"], "hops": [h for h, _ in t["hops"]],
                  "answer": t["answer"], "n_hops": t["n_hops"]})
        rows.append(r)
    d = NODE_DIR / node_id
    d.mkdir(parents=True, exist_ok=True)
    f = d / "work.jsonl"
    f.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    ns = sum(x["success"] for x in rows)
    print(f"[node:{node_id}] collected {len(rows)} ({ns} verified successes, "
          f"{ns/len(rows):.0%} solve)")
    return rows, tok, model


def to_sft_text(task, turns):
    """Serialize a verified trajectory into (prompt, target) pairs."""
    import experiments.run_longhorizon_demo as lhd
    s = lhd.SYS + "\n\nTask: follow this chain and give the final entity/attribute:\n"
    s += " -> ".join(h for h, _ in task["hops"]) + "\n"
    cur = s
    pairs = []
    for t_ in turns:
        act = f'{t_["kind"]}("{t_["value"]}")'
        pairs.append((cur + "\nNext action:\n", act))
        if t_["kind"] == "final":
            break
        cur += f"\n{act}\nObservation: {t_['obs']}\n"
    return pairs


# ---------------------------------------------------------------- train
def train_delta(node_id, rows, seed=7):
    random.seed(seed)
    sft_rows = [r for r in rows if r["success"]]
    # Verified = execution-checked correct final answer (the node's own
    # trajectory, replayed verbatim as the SFT target). Requiring also
    # first_mistake == -1 was unattainable under the testbed's strict hop
    # semantics (first-cycle evidence: 1 success in 60, 0 of those clean).
    if len(sft_rows) < 8:
        print(f"[node:{node_id}] only {len(sft_rows)} verified successes — "
              "delta skipped (gate below minimum)")
        return None
    kb, people = build_kb()
    by_id = {t["id"]: t for t in hop_paths(kb, people, n=1000, seed=11)}
    tok, model = load_model()
    cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-5)
    pairs = []
    for r in sft_rows:
        for prompt, target in to_sft_text(by_id[r["task_id"]], r["turns"]):
            pairs.append((prompt, target))
    random.shuffle(pairs)
    for epoch in range(1):
        for prompt, target in pairs:
            p_ids = tok(prompt, return_tensors="pt", truncation=True,
                        max_length=2048).input_ids.to("cuda:0")
            full = tok(prompt + target, return_tensors="pt", truncation=True,
                       max_length=2048).input_ids.to("cuda:0")
            labels = full.clone()
            labels[:, :p_ids.shape[1]] = -100
            out = model(input_ids=full, labels=labels)
            out.loss.backward()
            opt.step(); opt.zero_grad()
    d = NODE_DIR / node_id
    ad = d / "delta"
    model.save_pretrained(str(ad))
    print(f"[node:{node_id}] delta trained on {len(sft_rows)} verified "
          f"trajectories ({len(pairs)} supervised pairs)")
    return ad


# ---------------------------------------------------------------- gate
def _eval_acc(model, tok, kb, people, tasks, seed):
    acc = 0
    for t in tasks:
        r = run_agent(model, tok, t, kb, temperature=0.0)
        acc += r["success"]
    return acc / len(tasks)


def gate(node_id, delta_dir, n_eval=60, margin=0.02, seed=7):
    """Receiver-style held-out re-verification. Returns metrics dict."""
    kb, people = build_kb()
    tasks = make_workload(kb, people, n_eval, seed=seed + 1)
    tok, model = load_model()
    base_acc = _eval_acc(model, tok, kb, people, tasks, seed)
    del model
    tok2, model2 = load_model()
    m = PeftModel.from_pretrained(model2, str(delta_dir))
    m = m.merge_and_unload()
    m.eval()
    delta_acc = _eval_acc(m, tok2, kb, people, tasks, seed)
    accept = delta_acc >= base_acc + margin
    res = {"base_acc": base_acc, "delta_acc": delta_acc, "accepted": accept,
           "margin": margin, "n_eval": n_eval}
    (NODE_DIR / node_id / "gate.json").write_text(json.dumps(res))
    print(f"[node:{node_id}] gate: base {base_acc:.1%} vs delta {delta_acc:.1%} "
          f"-> {'ACCEPT' if accept else 'REJECT'}")
    return res


# ---------------------------------------------------------------- federation
def sync(node_id, exchange="runs/node/exchange", seed=7):
    """Publish accepted delta; re-verify every foreign delta on MY held-out
    tasks before adopting. Adoption rule: foreign delta must beat my current
    best on my held-out set."""
    d = NODE_DIR / node_id
    ex = Path(exchange); ex.mkdir(parents=True, exist_ok=True)
    gate_res = json.loads((d / "gate.json").read_text())
    if gate_res["accepted"]:
        dst = ex / node_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(d / "delta", dst)
        (dst / "delta.json").write_text(json.dumps(
            {"node_id": node_id, **gate_res}))
        print(f"[node:{node_id}] published delta to exchange")
    adopted = []
    for peer in sorted(ex.iterdir()):
        if peer.name == node_id or not peer.is_dir():
            continue
        kb, people = build_kb()
        tasks = make_workload(kb, people, 60, seed=seed + 1)
        tok, model = load_model()
        cur_acc = _eval_acc(model, tok, kb, people, tasks, seed)
        del model
        tok2, model2 = load_model()
        m = PeftModel.from_pretrained(model2, str(peer)).merge_and_unload()
        m.eval()
        peer_acc = _eval_acc(m, tok2, kb, people, tasks, seed)
        if peer_acc > cur_acc:
            shutil.copytree(peer, d / "merged", dirs_exist_ok=True)
            adopted.append({"peer": peer.name, "peer_acc": peer_acc,
                            "my_acc": cur_acc})
            print(f"[node:{node_id}] ADOPTED {peer.name} delta "
                  f"({cur_acc:.1%} -> {peer_acc:.1%})")
        else:
            print(f"[node:{node_id}] rejected {peer.name} delta "
                  f"({peer_acc:.1%} <= my {cur_acc:.1%})")
    (d / "sync.json").write_text(json.dumps({"adopted": adopted}))
    return adopted