"""Cumulative-error monitor prototype (docs/fmd_phase0_verdict.md follow-up #3).

Measures what the Learning Node self-monitor buys in tokens:
  - collect N sampled traces with per-step hidden states (causal decode = streaming-
    equivalent states)
  - train the loc_cum probe on the EXISTING Phase-0 labeled set (runs/fmd_phase0)
  - simulate two policies over fresh traces:
      unmonitored: every rollout runs to completion (EOS or 512)
      monitored:   abort a rollout at the first step whose probe P(error-occurred)
                   exceeds tau (tuned on the Phase-0 train split)
  - report: solve rate (must not drop), tokens per correct solution, tokens saved
No judge labels needed for the fresh traces (correctness comes from gold answers).

Usage: python -m experiments.run_monitor_proto [--n-problems 250] [--n-per 2]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.cartography.battery import load, is_correct
from src.fmd.phase0 import split_steps, extract_states, train_probe
from src.loop.train_arm import PROMPT

OUT = Path("runs/monitor_proto")
PH0 = Path("runs/fmd_phase0")
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
MON_LAYER = 15          # loc_cum best layer from the sampled Phase-0 run


def load_model():
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                           bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(MODEL)
    m = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=q,
                                             dtype=torch.bfloat16, device_map="cuda:0")
    m.eval()
    return tok, m


def train_loc_cum_probe():
    """Train on the Phase-0 sampled labeled set (states.pt has per-step states)."""
    data = torch.load(PH0 / "states.pt", weights_only=False)
    feats, meta = data["feats"], data["meta"]
    X, y = [], []
    for i, m in enumerate(meta):
        if m["correct"] or m["first_mistake"] < 0:
            continue
        n, fm = m["n_steps"], m["first_mistake"]
        for s in range(n):
            X.append(feats[i][MON_LAYER][s])
            y.append(1 if s >= fm else 0)
    # negatives from correct traces (all steps are pre-error by definition)
    for i, m in enumerate(meta):
        if m["correct"]:
            for s in range(m["n_steps"]):
                X.append(feats[i][MON_LAYER][s])
                y.append(0)
    clf = train_probe(np.stack(X), np.array(y))
    print(f"[proto] loc_cum probe trained on {len(y)} step-states "
          f"({sum(y)} post-error)")
    return clf


@torch.no_grad()
def collect(tok, model, problems, n_per, seed):
    import random
    rng = random.Random(seed); rng.shuffle(problems)
    rows = []
    for s in range(0, len(problems), 8):
        chunk = problems[s:s + 8]
        prompts = [PROMPT.format(q=p["question"]) for p in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to("cuda:0")
        gen = model.generate(**enc, max_new_tokens=512, do_sample=True, temperature=0.7,
                             top_p=0.95, num_return_sequences=n_per,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j, p in enumerate(chunk):
            for k in range(n_per):
                text = tok.decode(gen[j * n_per + k][enc["input_ids"].shape[1]:],
                                  skip_special_tokens=True)
                ntok = int((gen[j * n_per + k][enc["input_ids"].shape[1]:] !=
                            (tok.pad_token_id or tok.eos_token_id)).sum())
                rows.append({"id": p["id"], "question": p["question"], "answer": p["answer"],
                             "trace": text, "gen_tokens": ntok,
                             "correct": is_correct(text, p["answer"])})
        print(f"[proto] collected {min(s+8, len(problems))}/{len(problems)} problems")
    return rows


def simulate(rows, clf, tok, model, taus):
    """Embed fresh traces once, then evaluate both policies at several thresholds."""
    traces_file = OUT / "embedded.pt"
    if traces_file.exists():
        emb = torch.load(traces_file, weights_only=False)
        states_list = emb["states"]
        for i, r in enumerate(rows):
            r["n_steps"] = emb["meta"][i]["n_steps"]
    else:
        states_list, meta = [], []
        torch.cuda.empty_cache()
        for i, r in enumerate(rows):
            st = extract_states(model, tok, r["question"], r["trace"], [MON_LAYER])
            states_list.append(st[MON_LAYER])
            meta.append({"n_steps": st["n_steps"]})
            r["n_steps"] = st["n_steps"]
            if (i + 1) % 50 == 0:
                print(f"[proto] embedded {i+1}/{len(rows)}")
        torch.save({"states": states_list, "meta": meta}, traces_file)

    results = {}
    for tau in taus:
        tot_tokens, n_correct, n_aborted, saved = 0, 0, 0, 0
        for i, r in enumerate(rows):
            st = states_list[i]
            n_steps = r["n_steps"]
            abort_at = None
            for s in range(n_steps):
                p_err = float(clf.predict_proba(st[s][None, :])[0, 1])
                if p_err > tau:
                    abort_at = s
                    break
            if abort_at is None:
                cost = r["gen_tokens"]
            else:
                # tokens actually generated up to the abort step
                frac = (abort_at + 1) / max(1, n_steps)
                cost = int(r["gen_tokens"] * frac) + 8   # + small restart header cost
                n_aborted += 1
                if not r["correct"]:
                    saved += r["gen_tokens"] - cost
            tot_tokens += cost
            if abort_at is None and r["correct"]:
                n_correct += 1
        results[tau] = {
            "solve_rate_kept": round(n_correct / len(rows), 4),
            "tokens_per_correct": round(tot_tokens / max(1, n_correct)),
            "aborted": n_aborted,
            "tokens_saved_on_wrong": saved,
        }
    base_tokens = sum(r["gen_tokens"] for r in rows)
    base_correct = sum(r["correct"] for r in rows)
    baseline = {"solve_rate": round(base_correct / len(rows), 4),
                "tokens_per_correct": round(base_tokens / max(1, base_correct))}
    return baseline, results


def main(n_problems=250, n_per=2, seed=41):
    OUT.mkdir(parents=True, exist_ok=True)
    clf = train_loc_cum_probe()
    tok, model = load_model()
    if (OUT / "traces.jsonl").exists():
        rows = [json.loads(l) for l in (OUT / "traces.jsonl").read_text().splitlines() if l.strip()]
        print(f"[proto] loaded {len(rows)} cached traces")
    else:
        pool = load("probes/pool_train.jsonl")[:n_problems]
        rows = collect(tok, model, pool, n_per, seed)
        (OUT / "traces.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"[proto] {len(rows)} traces, base solve rate "
          f"{sum(r['correct'] for r in rows)/len(rows):.1%}")
    taus = [0.5, 0.6, 0.7, 0.8, 0.9]
    baseline, results = simulate(rows, clf, tok, model, taus)
    print(f"[proto] UNMONITORED baseline: solve {baseline['solve_rate']:.1%}, "
          f"{baseline['tokens_per_correct']} tokens/correct")
    for tau, r in results.items():
        print(f"[proto] tau={tau}: solve_kept {r['solve_rate_kept']:.1%}, "
              f"tokens/correct {r['tokens_per_correct']} "
              f"(aborted {r['aborted']}, saved {r['tokens_saved_on_wrong']} tok)")
    (OUT / "proto_result.json").write_text(json.dumps(
        {"baseline": baseline, "monitored": {str(t): v for t, v in results.items()},
         "n_traces": len(rows), "mon_layer": MON_LAYER, "seed": seed}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-problems", type=int, default=250)
    ap.add_argument("--n-per", type=int, default=2)
    ap.add_argument("--seed", type=int, default=41)
    a = ap.parse_args()
    main(a.n_problems, a.n_per, a.seed)