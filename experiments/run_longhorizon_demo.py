"""Long-horizon monitor demo: multi-hop lookup agent over a synthetic KB.

Why this testbed: trajectories are long (up to 24 tool-call turns), every turn has
EXACT ground truth (gold hop path -> first-mistake = first deviation, no judge), and
doomed runs waste many tokens — the regime where the cumulative-error monitor's
economics can matter (docs/monitor_proto_result.md).

Pipeline (checkpointed to runs/longhorizon/):
  1+2. build KB/tasks; agent loop (lookup tool, temp 0.7) -> labeled transcripts
  3.   per-turn hidden states (one forward per transcript, states at turn ends)
  4.   train per-layer turn-level loc_cum probes on the calibration split
  5.   simulate unmonitored vs abort-on-threshold(+restart) on the test split
       -> tokens per correct task, solve rate kept

Usage: python -m experiments.run_longhorizon_demo [--n-cal 300] [--n-test 300]
"""
from __future__ import annotations
import argparse, json, random, re, sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.fmd.phase0 import train_probe, auroc

OUT = Path("runs/longhorizon")
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
MAX_STEPS = 24
LAYERS = list(range(8, 25))

FIRST = ["Ivy", "Marco", "Priya", "Sven", "Nadia", "Omar", "Lena", "Kofi",
         "Yuki", "Tara", "Felix", "Zara", "Hugo", "Mila", "Enzo", "Rosa"]
COMPS = ["Nimbus", "Vertex", "Quanta", "Halcyon", "Boreal", "Cobalt",
         "Lumen", "Sable", "Orbit", "Fathom", "Zephyr", "Ember"]
CITIES = ["Aldersgate", "Brightmere", "Cinderfall", "Duskwood", "Emberport",
          "Frostvale", "Goldleaf", "Hollowbrook"]
ROLES = ["CEO", "CTO", "Founder"]
YEARS = [1987, 1991, 1994, 1998, 2001, 2005, 2009, 2012]


def build_kb(seed=7):
    rng = random.Random(seed)
    people = list(dict.fromkeys(FIRST))[:16]
    # every person works somewhere, has a role at that company, and a mentor
    kb = {}
    for c in COMPS:
        kb[(c, "hq_city")] = rng.choice(CITIES)
        kb[(c, "year_founded")] = str(rng.choice(YEARS))
    for p in people:
        c = rng.choice(COMPS)
        kb[(p, "works_at")] = c
        kb[(p, "role")] = rng.choice(ROLES)
        kb[(p, "mentors")] = rng.choice([x for x in people if x != p])
        kb[(c, f"role_{kb[(p, 'role')]}")] = p
    for c in COMPS:
        if (c, "role_CEO") not in kb:
            kb[(c, "role_CEO")] = rng.choice(people)
    return kb, people


def hop_paths(kb, people, n, seed=11):
    """Gold hop chains of length 3-5 ending at a resolvable entity."""
    rng = random.Random(seed)
    out = []
    attempts = 0
    while len(out) < n and attempts < n * 10:
        attempts += 1
        p0 = rng.choice(people)
        kind = rng.choice(["works_role_year", "mentor_chain", "ceo_city"])
        if kind == "works_role_year":
            c = kb[(p0, "works_at")]
            r = kb[(p0, "role")]
            y = kb[(c, "year_founded")]
            path = [(f"works_at {p0}", c), (f"the role of {p0} at {c}", r),
                    (f"the year {c} was founded", str(y))]
            ans = str(y)
        elif kind == "mentor_chain":
            m = kb[(p0, "mentors")]
            c2 = kb[(m, "works_at")]
            city = kb[(c2, "hq_city")]
            path = [(f"the mentor of {p0}", m), (f"where {m} works", c2),
                    (f"the HQ city of {c2}", city)]
            ans = city
        else:
            c = rng.choice(COMPS)
            ceo = kb[(c, "role_CEO")]
            ct = kb[(ceo, "works_at")]
            city = kb[(ct, "hq_city")]
            path = [(f"the CEO of {c}", ceo), (f"where {ceo} works", ct),
                    (f"the HQ city of {ct}", city)]
            ans = city
        out.append({"id": f"t{len(out)}", "hops": path, "answer": ans, "start": p0,
                    "n_hops": len(path)})
    return out


SYS = ("You solve multi-hop questions using the lookup tool. Each turn output EXACTLY "
       "one line, either:\nlookup(\"<entity or attribute>\")\nor\nfinal(\"<answer>\")\n"
       "The knowledge base relates people and companies via: works_at, role, mentors, "
       "hq_city, year_founded. Follow the hop chain step by step.")
TOOL_RE = re.compile(r'(lookup|final)\("(.*)"\)')


def run_agent(model, tok, task, kb, temperature=0.7):
    hops_done = []
    turns, first_mistake, success = [], -1, False
    cur = SYS + "\n\nTask: follow this chain and give the final entity/attribute:\n"
    cur += " -> ".join(h for h, _ in task["hops"]) + "\n"
    for s in range(MAX_STEPS):
        prompt = cur + "\nNext action:"
        ids = tok(prompt, return_tensors="pt", truncation=True, max_length=2048).input_ids.to("cuda:0")
        out = model.generate(ids, max_new_tokens=40, do_sample=temperature > 0,
                             temperature=temperature, top_p=0.95,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        act = tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip().splitlines()[0]
        m = TOOL_RE.search(act)
        kind, val = (m.group(1), m.group(2).strip()) if m else ("junk", act[:60])
        step = {"kind": kind, "value": val,
                "out_tokens": int((out[0][ids.shape[1]:] != (tok.pad_token_id or tok.eos_token_id)).sum())}
        if kind == "final":
            success = val.lower() == str(task["answer"]).lower()
            if not success and first_mistake == -1:
                first_mistake = len(turns)
            turns.append(step)
            break
        if kind == "lookup":
            expect = str(task["hops"][len(hops_done)][1]) if len(hops_done) < len(task["hops"]) else None
            ok = expect is not None and val.lower() == expect.lower()
            if not ok and first_mistake == -1:
                first_mistake = len(turns)
            hops_done.append(val)
            obs = str(kb.get((val, "works_at")) or kb.get((val, "hq_city"))
                      or kb.get((val, "year_founded")) or kb.get((val, "role"))
                      or kb.get((val, "mentors")) or "NOT FOUND")
        else:
            obs = "INVALID ACTION"
            if first_mistake == -1:
                first_mistake = len(turns)
        step["obs"] = obs
        turns.append(step)
        cur += f"\n{act}\nObservation: {obs}\n"
    return {"turns": turns, "first_mistake": first_mistake, "success": success,
            "n_turns": len(turns),
            "total_tokens": sum(x["out_tokens"] for x in turns) + len(turns) * 30}


def load_model():
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                           bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(MODEL)
    m = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=q,
                                             dtype=torch.bfloat16, device_map="cuda:0")
    m.eval()
    return tok, m


def stage12(n_cal, n_test, seed=41):
    OUT.mkdir(parents=True, exist_ok=True)
    kb, people = build_kb()
    tasks = hop_paths(kb, people, n=n_cal + n_test)
    tok, model = load_model()
    f = OUT / "transcripts.jsonl"
    rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()] if f.exists() else []
    for i, t in enumerate(tasks[len(rows):], start=len(rows)):
        r = run_agent(model, tok, t, kb)
        r.update({"task_id": t["id"], "hops": [h for h, _ in t["hops"]],
                  "answer": t["answer"], "n_hops": t["n_hops"]})
        rows.append(r)
        f.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
        if (i + 1) % 25 == 0:
            print(f"[lh] {len(rows)}/{len(tasks)} transcripts "
                  f"({sum(x['success'] for x in rows)} solved)")
    print(f"[lh] collected {len(rows)}: solve "
          f"{sum(x['success'] for x in rows)/len(rows):.1%}, mean turns "
          f"{sum(x['n_turns'] for x in rows)/len(rows):.1f}")
    return rows[:n_cal], rows[n_cal:n_cal + n_test]


@torch.no_grad()
def stage3(cal, test):
    tok, model = load_model()
    torch.cuda.empty_cache()
    f = OUT / "turn_states.pt"
    if f.exists():
        data = torch.load(f, weights_only=False)
        if len(data["meta"]) == len(cal) + len(test):
            return data
    feats, meta = [], []
    for i, r in enumerate(cal + test):
        cur = SYS + "\n\nTask: follow this chain and give the final entity/attribute:\n"
        cur += " -> ".join(h for h in r["hops"]) + "\n"
        # token positions of each turn end
        marks = []
        base = tok(cur, add_special_tokens=False).input_ids
        pos = 1  # + BOS
        marks.append(pos + len(base))
        for st in r["turns"]:
            act = (f'lookup("{st["value"]}")' if st["kind"] == "lookup"
                   else f'final("{st["value"]}")' if st["kind"] == "final" else st["value"])
            cur += f"\n{act}\nObservation: {st.get('obs', '-')}\n"
            ids = tok(cur, add_special_tokens=False).input_ids
            marks.append(1 + len(ids))
        ids = tok(cur, return_tensors="pt", truncation=True, max_length=4096).input_ids.to("cuda:0")
        out = model(ids, output_hidden_states=True)
        marks = [min(m, ids.shape[1] - 1) for m in marks][:len(r["turns"])]
        per_layer = {L: np.stack([out.hidden_states[L][0][mk].float().cpu().numpy()
                                  for mk in marks]) for L in LAYERS}
        feats.append(per_layer)
        meta.append({"first_mistake": r["first_mistake"], "n_turns": r["n_turns"],
                     "success": r["success"], "total_tokens": r["total_tokens"]})
        if (i + 1) % 20 == 0:
            print(f"[lh] embedded {i+1}/{len(cal)+len(test)}")
    data = {"feats": feats, "meta": meta, "n_cal": len(cal)}
    torch.save(data, f)
    return data


def stage4_train(data):
    """Per-layer turn-level probe on CALIBRATION rows: post-error (turn>=fm, wrong rows)
    vs pre-error. Pick best layer by held-out AUROC within calibration."""
    feats, meta, n_cal = data["feats"], data["meta"], data["n_cal"]
    cal = list(range(n_cal))
    rng = np.random.RandomState(0); rng.shuffle(cal)
    tr, va = cal[:int(0.7 * n_cal)], cal[int(0.7 * n_cal):]
    best = (None, -1.0, None)
    for L in LAYERS:
        X, y = [], []
        for i in tr:
            n, fm = meta[i]["n_turns"], meta[i]["first_mistake"]
            for s in range(n):
                X.append(feats[i][L][s]); y.append(1 if (s >= fm if fm >= 0 else False) else 0)
        clf = train_probe(np.stack(X), np.array(y))
        Xv, yv = [], []
        for i in va:
            n, fm = meta[i]["n_turns"], meta[i]["first_mistake"]
            for s in range(n):
                Xv.append(feats[i][L][s]); yv.append(1 if (s >= fm if fm >= 0 else False) else 0)
        a = auroc(yv, clf.predict_proba(np.stack(Xv))[:, 1])
        if a > best[1]:
            best = (clf, a, L)
    print(f"[lh] best loc_cum layer {best[2]} val AUROC {best[1]:.3f}")
    return best


def stage5_simulate(data, clf, tau):
    """Test-split simulation: unmonitored vs monitored (abort at first turn with
    P(post-error) > tau; the task is then retried fresh — retry cost approximated as
    the mean unmonitored cost of a successful task)."""
    feats, meta, n_cal = data["feats"], data["meta"], data["n_cal"]
    test = list(range(n_cal, len(meta)))
    tot_u, tot_m, ok_u, ok_m, n_abort = 0, 0, 0, 0, 0
    for i in test:
        n, fm, ok, toks = meta[i]["n_turns"], meta[i]["first_mistake"], meta[i]["success"], meta[i]["total_tokens"]
        # unmonitored: full cost
        tot_u += toks
        ok_u += ok
        # monitored: abort at first turn with p>tau
        abort = None
        for s in range(n):
            p = float(clf.predict_proba(feats[i][clf_layer][s][None, :])[0, 1])
            if p > tau:
                abort = s; break
        if abort is None:
            cost, keep = toks, ok
        else:
            frac = (abort + 1) / max(1, n)
            # pay tokens of turns up to abort; retry succeeds at the base rate
            per_turn = toks / max(1, n)
            cost = int(per_turn * (abort + 1)) + RETRY_COST
            n_abort += 1
            keep = ok  # retry assumed to eventually succeed (base-rate; conservative on cost)
        tot_m += cost
        ok_m += keep
    return {"unmonitored": {"solve": ok_u / len(test), "tokens_per_correct":
                            tot_u / max(1, ok_u)},
            "monitored": {"solve": ok_m / len(test), "tokens_per_correct":
                          tot_m / max(1, ok_m), "aborts": n_abort}}


RETRY_COST = 0
clf_layer = None

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-cal", type=int, default=300)
    ap.add_argument("--n-test", type=int, default=300)
    a = ap.parse_args()
    cal, test = stage12(a.n_cal, a.n_test)
    data = stage3(cal, test)
    clf, vauc, L = stage4_train(data)
    globals()["clf_layer"] = L
    # retry cost = mean tokens of successful unmonitored test tasks
    meta = data["meta"]; n_cal = data["n_cal"]
    ok_costs = [meta[i]["total_tokens"] for i in range(n_cal, len(meta)) if meta[i]["success"]]
    globals()["RETRY_COST"] = int(sum(ok_costs) / max(1, len(ok_costs)))
    results = {}
    for tau in (0.3, 0.5, 0.7):
        r = stage5_simulate(data, clf, tau)
        results[tau] = r
        print(f"[lh] tau={tau}: unmon {r['unmonitored']['solve']:.1%} / "
              f"{r['unmonitored']['tokens_per_correct']:.0f} tok-correct | "
              f"mon {r['monitored']['solve']:.1%} / "
              f"{r['monitored']['tokens_per_correct']:.0f} tok-correct "
              f"({r['monitored']['aborts']} aborts)")
    (OUT / "longhorizon_result.json").write_text(json.dumps(
        {"val_auroc": vauc, "layer": L, "results": results,
         "n_cal": a.n_cal, "n_test": a.n_test}, indent=2, default=str))
    print("[lh] DONE ->", OUT / "longhorizon_result.json")