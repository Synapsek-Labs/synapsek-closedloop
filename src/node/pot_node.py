# PoT node workload — the registered fix for the wandering-trajectory defect
#
# Diagnosis (docs/learning_node_mvp_result.md Addendum 2): the multi-turn
# lookup testbed's reward is gameable and ZERO clean demonstrations exist.
# Fix: single-shot program-of-thought tasks on the GSM8K train pool.
# One generation per task -> no wandering possible. Verification = hard
# execution matching against the gold answer.
#
# Teacher (7B) generates; student (1.5B) trains on verified teacher
# programs; gate = held-out battery solve rate, +2% margin, unchanged.
from __future__ import annotations
import json, random
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model

from src.loop.pot_runner import run_one
from src.cartography.battery import extract_last_number, is_correct
from src.loop.synthesizer import POT_PROMPT, _extract_code
from src.node.nightly import NODE_DIR
from experiments.run_longhorizon_demo import load_model  # student loader (1.5B)

POOL = Path("probes/pool_train.jsonl")
HELD = Path("probes/battery_held_out.jsonl")


def _ensure_split():
    if not POOL.exists() or not HELD.exists():
        from src.cartography.battery import build
        build()
    pool = [json.loads(l) for l in POOL.open(encoding="utf-8") if l.strip()]
    held = [json.loads(l) for l in HELD.open(encoding="utf-8") if l.strip()]
    return pool, held


def collect_teacher_pot(node_id, n_target=150, max_problems=600, seed=7):
    """Teacher writes one PoT program per problem; keep execution-verified ones."""
    from src.node.teacher import load_teacher, TEACHER as TEACHER_ID
    pool, held = _ensure_split()
    rng = random.Random(seed)
    work = rng.sample(pool, min(max_problems, len(pool)))
    ttok, tmodel = load_teacher()
    ttok.padding_side = "left"   # batched decoder-only generation requires left-padding
    rows, done = [], 0
    B = 16
    for i in range(0, len(work), B):
        chunk = work[i:i + B]
        prompts = [POT_PROMPT.format(q=p["question"]) for p in chunk]
        ids = ttok(prompts, return_tensors="pt", padding=True,
                   truncation=True, max_length=1024).to("cuda:0")
        out = tmodel.generate(**ids, max_new_tokens=768, do_sample=False,
                              pad_token_id=ttok.pad_token_id or ttok.eos_token_id)
        for j, p in enumerate(chunk):
            text = ttok.decode(out[j][ids["input_ids"].shape[1]:],
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
                             "teacher": True,
                             "teacher_id": TEACHER_ID})
        done += len(chunk)
        print(f"[pot] {done}/{len(work)} problems, {len(rows)} verified "
              f"programs", flush=True)
        if len(rows) >= n_target:
            break
    d = NODE_DIR / node_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "work_pot.jsonl").write_text(
        "\n".join(json.dumps(x) for x in rows) + "\n")
    print(f"[pot] collected {len(rows)} verified teacher programs")
    return rows


CF_PROMPT = "<|im_start|>assistant\n"  # context-free: assistant continues from nothing


def _gen_replay(model, tok, n=150, batch=16, max_new=400, seed=7):
    """Context-free generations from the base model = replay anchor data."""
    torch.manual_seed(seed)
    out_pairs, seen = [], 0
    while seen < n:
        b = min(batch, n - seen)
        prompts = [CF_PROMPT] * b
        ids = tok(prompts, return_tensors="pt", padding=True).to(model.device)
        g = model.generate(**ids, max_new_tokens=max_new, do_sample=True,
                           temperature=1.0, top_p=0.95,
                           pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j in range(b):
            text = tok.decode(g[j][ids["input_ids"].shape[1]:],
                              skip_special_tokens=True).strip()
            if len(text) > 40:
                out_pairs.append((CF_PROMPT, text))
        seen += b
    return out_pairs


def train_student_pot(node_id, rows, n_epochs=1, lr=5e-5, seed=7,
                      out_name="delta_pot", replay_ratio=1.0, replay_n=None):
    """Validated v2 recipe (learning_node_v2_plan.md): teacher pairs MIXED
    with context-free base-model replay (arXiv:2505.13811) — the change
    that turned 7 rejections into the first ACCEPT (47->50)."""
    random.seed(seed)
    if len(rows) < 40:
        print(f"[pot] only {len(rows)} verified programs — below minimum")
        return None
    tok, model = load_model()
    if replay_ratio > 0:
        replay = _gen_replay(model, tok,
                             n=int(len(rows) * replay_ratio)
                             if replay_n is None else replay_n)
        pairs = [(POT_PROMPT.format(q=r["question"]), r["program"]) for r in rows]
        pairs = pairs + replay
    else:
        pairs = [(POT_PROMPT.format(q=r["question"]), r["program"]) for r in rows]
    random.shuffle(pairs)
    print(f"[pot] training on {len(pairs)} pairs "
          f"({len(rows)} teacher + {len(pairs)-len(rows)} replay)")
    cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=lr)
    for _ in range(n_epochs):
        for prompt, target in pairs:
            p_ids = tok(prompt, return_tensors="pt", truncation=True,
                        max_length=1024).input_ids.to("cuda:0")
            full = tok(prompt + target, return_tensors="pt", truncation=True,
                       max_length=2048).input_ids.to("cuda:0")
            labels = full.clone()
            labels[:, :p_ids.shape[1]] = -100
            out = model(input_ids=full, labels=labels)
            out.loss.backward()
            opt.step(); opt.zero_grad()
    ad = NODE_DIR / node_id / out_name
    model.save_pretrained(str(ad))
    print(f"[pot] student delta trained on {len(rows)} teacher programs "
          f"-> {ad}")
    return ad


def eval_pot(model, tok, tasks, label="eval", batch=8):
    """Held-out battery PoT solve rate for ANY model (base or adapter).
    Programs execute in an isolated subprocess (GIL-deadlock-proof)."""
    acc = 0
    for i in range(0, len(tasks), batch):
        chunk = tasks[i:i + batch]
        prompts = [POT_PROMPT.format(q=t["question"]) for t in chunk]
        ids = tok(prompts, return_tensors="pt", padding=True,
                  truncation=True, max_length=1024).to(model.device)
        out = model.generate(**ids, max_new_tokens=768, do_sample=False,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        codes, goids = [], []
        for j, t in enumerate(chunk):
            text = tok.decode(out[j][ids["input_ids"].shape[1]:],
                              skip_special_tokens=True)
            code = _extract_code(text)
            if code:
                codes.append({"idx": len(codes), "code": code})
                goids.append((len(codes) - 1, t))
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(codes, f); cf = f.name
        rf = cf + ".res"
        res = {}
        try:
            import sys
            subprocess.run([sys.executable, "-m",
                            "src.loop.pot_runner", cf, rf],
                           timeout=600, capture_output=True)
            # pot_runner writes results incrementally as JSON lines;
            # parse line-tolerantly (torn final line is normal)
            for line in open(rf, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    res[r["idx"]] = r
                except Exception:
                    continue
        except Exception as e:
            print(f"[pot-gate:{label}] exec batch failed ({e}) — "
                  f"{len(goids)} problems lost", flush=True)
            res = {}
        finally:
            for p in (cf, rf):
                try: os.unlink(p)
                except OSError: pass
        for idx, t in goids:
            r = res.get(idx)
            gold = extract_last_number(t["answer"])
            if r and r.get("ok") and r.get("number") is not None and \
                    gold is not None and abs(r["number"] - gold) < 1e-4:
                acc += 1
        print(f"[pot-gate:{label}] batch {i//batch + 1}/"
              f"{(len(tasks)+batch-1)//batch} cum_acc={acc}", flush=True)
    return acc / len(tasks)


def gate_pot(node_id, delta_dir, n_eval=100, margin=0.02, seed=7):
    """Held-out battery PoT solve: base vs base+delta. +2% margin."""
    from peft import PeftModel
    _, held = _ensure_split()
    rng = random.Random(seed)
    tasks = rng.sample(held, min(n_eval, len(held)))
    tok, model = load_model()
    tok.padding_side = "left"

    base_acc = eval_pot(model, tok, tasks, label="base")
    del model
    torch.cuda.empty_cache()
    tok2, model2 = load_model()
    tok2.padding_side = "left"
    m = PeftModel.from_pretrained(model2, str(delta_dir)).merge_and_unload()
    m.eval()
    delta_acc = eval_pot(m, tok2, tasks, label="delta")
    accept = delta_acc >= base_acc + margin
    res = {"base_acc": base_acc, "delta_acc": delta_acc, "accepted": accept,
           "n_eval": len(tasks), "margin": margin, "substrate": "pot"}
    (NODE_DIR / node_id / "gate_pot.json").write_text(json.dumps(res))
    print(f"[pot-gate] base {base_acc:.1%} vs delta {delta_acc:.1%} "
          f"-> {'ACCEPT' if accept else 'REJECT'}")
    return res


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, ".")
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--target", type=int, default=150)
    ap.add_argument("--gate-only", action="store_true")
    ap.add_argument("--delta", default="delta_pot")
    a = ap.parse_args()
    if a.gate_only:
        gate_pot(a.node, NODE_DIR / a.node / a.delta)
        sys.exit(0)
    rows = collect_teacher_pot(a.node, a.target)
    ad = train_student_pot(a.node, rows)
    if ad is None:
        sys.exit(0)
    from src.node.bank import add_to_bank
    import time
    add_to_bank(a.node, ad, name=f"pot-{time.strftime('%Y%m%d')}")
    print("[pot] collect+train+bank done -> run the full gate in a FRESH process:")
    print(f"  python -m src.node.pot_node --node {a.node} --gate-only")
