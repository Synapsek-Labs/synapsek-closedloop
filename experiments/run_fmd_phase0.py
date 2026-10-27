"""FMD Phase 0: feasibility gate (docs/fmd_plan.md).

Stages (each checkpointed to runs/fmd_phase0/ so stages resume):
  1. sample traces (n per problem, temp 0.7) from Qwen2.5-1.5B-Instruct on pool problems
  2. judge first-mistake step with Qwen2.5-7B-Instruct (wrong traces only)
  3. extract per-step hidden states (layers 8-24) for a balanced subset
  4. train per-layer linear probes: (a) trace correctness, (b) localization
  5. report mean±sd AUROC over 3 splits vs pre-registered thresholds

Usage: python -m experiments.run_fmd_phase0 [--stage 1|2|3|4] [--n-problems 250] [--n-per 8]
"""
from __future__ import annotations
import argparse, json, random, sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.cartography.battery import load, extract_last_number, is_correct
from src.fmd.phase0 import (split_steps, judge_first_mistake, extract_states,
                            train_probe, auroc)
from src.loop.train_arm import PROMPT

OUT = Path("runs/fmd_phase0")
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
JUDGE = "Qwen/Qwen2.5-7B-Instruct"
LAYERS = list(range(8, 25))


def load_model(name, _cache={}):
    if name not in _cache:
        from transformers import BitsAndBytesConfig
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_quant_type="nf4")
        tok = AutoTokenizer.from_pretrained(name)
        m = AutoModelForCausalLM.from_pretrained(name, quantization_config=q,
                                                 dtype=torch.bfloat16, device_map="cuda:0")
        m.eval()
        _cache[name] = (tok, m)
    return _cache[name]


@torch.no_grad()
def stage1(n_problems=250, n_per=8, seed=17):
    OUT.mkdir(parents=True, exist_ok=True)
    traces_file = OUT / "traces.jsonl"
    if traces_file.exists():
        print("[stage1] traces exist, skipping"); return
    pool = load("probes/pool_train.jsonl")[:n_problems]
    tok, model = load_model(MODEL)
    rng = random.Random(seed)
    rows = []
    for s in range(0, len(pool), 8):
        chunk = pool[s:s + 8]
        prompts = [PROMPT.format(q=p["question"]) for p in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to("cuda:0")
        gen = model.generate(**enc, max_new_tokens=512, do_sample=True, temperature=0.7,
                             top_p=0.95, num_return_sequences=n_per,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j, p in enumerate(chunk):
            for k in range(n_per):
                idx = j * n_per + k
                text = tok.decode(gen[idx][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                rows.append({"id": p["id"], "question": p["question"], "answer": p["answer"],
                             "sample": k, "trace": text,
                             "correct": is_correct(text, p["answer"])})
        print(f"[stage1] {min(s+8, len(pool))}/{len(pool)} problems done")
    traces_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    n_ok = sum(r["correct"] for r in rows)
    print(f"[stage1] {len(rows)} traces, {n_ok} correct ({n_ok/len(rows):.1%})")


def stage2(max_wrong=600, seed=17):
    f = OUT / "labeled.jsonl"
    if f.exists():
        print("[stage2] labels exist, skipping"); return
    rows = [json.loads(l) for l in (OUT / "traces.jsonl").read_text().splitlines() if l.strip()]
    wrong = [r for r in rows if not r["correct"]]
    rng = random.Random(seed); rng.shuffle(wrong)
    wrong = wrong[:max_wrong]
    right = [r for r in rows if r["correct"]]
    rng.shuffle(right); right = right[:max_wrong]
    tok, model = load_model(JUDGE)
    out = []
    for i, r in enumerate(wrong + right):
        if r["correct"]:
            fm = -1
        else:
            fm = judge_first_mistake(tok, model, r["question"], r["trace"])
        out.append({**r, "first_mistake": fm})
        if (i + 1) % 50 == 0:
            print(f"[stage2] {i+1}/{len(wrong)+len(right)} judged")
            f.write_text("\n".join(json.dumps(x) for x in out) + "\n")
    f.write_text("\n".join(json.dumps(x) for x in out) + "\n")
    n_fm = sum(1 for x in out if x["first_mistake"] >= 0)
    print(f"[stage2] labeled {len(out)} traces; judge found a first mistake in {n_fm}/{len(wrong)} wrong traces")


def stage3(max_traces=500, seed=17):
    f = OUT / "states.pt"
    if f.exists():
        print("[stage3] states exist, skipping"); return
    rows = [json.loads(l) for l in (OUT / "labeled.jsonl").read_text().splitlines() if l.strip()]
    rng = random.Random(seed); rng.shuffle(rows)
    rows = rows[:max_traces]
    tok, model = load_model(MODEL)
    torch.cuda.empty_cache()
    feats, meta = [], []
    for i, r in enumerate(rows):
        st = extract_states(model, tok, r["question"], r["trace"], LAYERS)
        n_steps = st["n_steps"]
        steps = split_steps(r["trace"])[:n_steps]
        fm = r["first_mistake"]
        for L in LAYERS:
            pass  # states stored per trace below
        feats.append({L: st[L] for L in LAYERS})
        meta.append({"correct": r["correct"], "first_mistake": fm,
                     "n_steps": n_steps, "id": r["id"]})
        if (i + 1) % 25 == 0:
            print(f"[stage3] {i+1}/{len(rows)} traces embedded")
            torch.save({"feats": feats, "meta": meta}, str(f) + ".tmp")
            (OUT / "states.pt").unlink(missing_ok=True)
            Path(str(f) + ".tmp").rename(f)
    torch.save({"feats": feats, "meta": meta}, f)
    print(f"[stage3] saved {len(feats)} traces")


def stage4():
    import numpy as np
    data = torch.load(OUT / "states.pt", weights_only=False)
    feats, meta = data["feats"], data["meta"]
    # (a) trace-level: last mark vector per layer, label = correct
    # (b) step-level localization: marks 0..n_steps-1; cumulative label (>= fm) and strict
    print(f"[stage4] {len(meta)} traces; {sum(m['correct'] for m in meta)} correct")
    results = {"trace": {}, "loc_cum": {}, "loc_strict": {}}
    for L in LAYERS:
        # trace-level
        X = np.stack([feats[i][L][meta[i]["n_steps"]] for i in range(len(meta))])
        y = np.array([0 if m["correct"] else 1 for m in meta])
        rs = []
        for sp in range(3):
            rng = np.random.RandomState(sp)
            idx = rng.permutation(len(y))
            tr, te = idx[:int(0.7 * len(y))], idx[int(0.7 * len(y)):]
            clf = train_probe(X[tr], y[tr])
            rs.append(auroc(y[te], clf.predict_proba(X[te])[:, 1]))
        results["trace"][L] = rs
        # localization: use only wrong traces
        widx = [i for i in range(len(meta)) if not meta[i]["correct"] and meta[i]["first_mistake"] >= 0]
        for key in ("loc_cum", "loc_strict"):
            Xw, yw = [], []
            for i in widx:
                n, fm = meta[i]["n_steps"], meta[i]["first_mistake"]
                for s in range(n):
                    Xw.append(feats[i][L][s])
                    yw.append(1 if (s >= fm if key == "loc_cum" else s == fm) else 0)
            Xw, yw = np.stack(Xw), np.array(yw)
            rs = []
            for sp in range(3):
                rng = np.random.RandomState(sp)
                idx = rng.permutation(len(yw))
                tr, te = idx[:int(0.7 * len(yw))], idx[int(0.7 * len(yw)):]
                clf = train_probe(Xw[tr], yw[tr])
                rs.append(auroc(yw[te], clf.predict_proba(Xw[te])[:, 1]))
            results[key][L] = rs
    report = {}
    for key, per_layer in results.items():
        best = max(per_layer.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        mean = sum(best[1]) / len(best[1])
        sd = (sum((x - mean) ** 2 for x in best[1]) / len(best[1])) ** 0.5
        report[key] = {"best_layer": best[0], "auroc_mean": round(mean, 4),
                       "auroc_sd": round(sd, 4), "splits": [round(x, 4) for x in best[1]]}
        print(f"[stage4] {key}: best layer {best[0]} AUROC {mean:.3f} ± {sd:.3f}")
    (OUT / "probe_report.json").write_text(json.dumps(
        {"report": report, "all_layers": {k: {str(l): v for l, v in d.items()}
                                          for k, d in results.items()}}, indent=2, default=str))
    a, b = report["trace"]["auroc_mean"], report["loc_cum"]["auroc_mean"]
    verdict = ("GO" if (a >= 0.85 and b >= 0.75) else
               "PIVOT-within-bet" if (a >= 0.85 and b >= 0.65) else "STOP-FMD-1.5B")
    print(f"[stage4] PRE-REGISTERED VERDICT: {verdict} "
          f"(trace {a:.3f}, loc_cum {b:.3f}, loc_strict {report['loc_strict']['auroc_mean']:.3f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, default=0, help="run stages 1..stage (0=all)")
    ap.add_argument("--n-problems", type=int, default=250)
    ap.add_argument("--n-per", type=int, default=8)
    args = ap.parse_args()
    stage1(args.n_problems, args.n_per)
    stage2()
    stage3()
    stage4()
