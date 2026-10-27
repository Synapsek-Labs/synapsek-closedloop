"""Self-Verified Distillation test (arXiv:2605.26132, verified 2026-10-28).

Invert the synthesis loop: sample N candidate CoT solutions per pool problem from the
1.5B policy, keep only candidates whose final answer matches an execution-verified
PoT consensus (2 independent programs agree), SFT 1 epoch on accepted solutions,
evaluate on the frozen held-out battery. Compare vs the Tier-0 static arm.

Usage: python -m experiments.run_svd [--n-problems 800] [--n-per 8] [--seed 17]
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.cartography.battery import load, is_correct, extract_last_number
from src.loop.train_arm import PROMPT, train_steps, probe as gen_greedy
from src.loop.synthesizer import _gen

import re as _re


def _code_of(text: str) -> str:
    """Robust extraction: continuation may have a closing fence but no opener."""
    code = text.split("```", 1)[0]          # cut at first closing fence (prompt opened it)
    lines = [l for l in code.strip().splitlines()
             if not _re.match(r"^(sure|here|this|note|i'll|let's)\b", l, re.I)]
    code = "\n".join(lines).strip()
    if not code or "print(" not in code or len(code) > 3000:
        return ""
    if any(p in code.lower() for p in ("input(", "while true", "while 1", "sleep(", "stdin")):
        return ""
    return code

OUT = Path("runs/svd")
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"


def load_model(name):
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                           bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(name)
    m = AutoModelForCausalLM.from_pretrained(name, quantization_config=q,
                                             dtype=torch.bfloat16, device_map="cuda:0")
    m.config.use_cache = True
    return tok, m


@torch.no_grad()
def pot_consensus(model, tok, question: str, max_new=768) -> float | None:
    """2 independent PoT programs; return their answer if both agree, else None."""
    import subprocess, tempfile
    prompt = ("Solve this with short straight-line Python code: no functions, no classes, "
              "no docstrings, no comments. Compute the answer step by step in plain "
              "variables, and the LAST line must be exactly: print(answer)\n\n"
              "Problem: " + question + "\n\n```python\n")
    codes = _gen(model, tok, [prompt, prompt], max_new)
    progs = []
    for t in codes:
        c = _code_of(t)
        if c and _re.search(r"print\s*\(", c):
            progs.append(c)
    if len(progs) < 2:
        return None
    vals = []
    exe = sys.executable
    for c in progs:
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
                f.write(c); path = f.name
            r = subprocess.run([exe, path], capture_output=True, text=True, timeout=15)
            v = extract_last_number(r.stdout)
            if v is not None:
                vals.append(v)
        except Exception:
            pass
    if len(vals) == 2 and abs(vals[0] - vals[1]) < 1e-6:
        return vals[0]
    return None


def main(n_problems=800, n_per=8, seed=17):
    OUT.mkdir(parents=True, exist_ok=True)
    pool = load("probes/pool_train.jsonl")
    import random
    rng = random.Random(seed); rng.shuffle(pool)
    pool = pool[:n_problems]

    tok, model = load_model(MODEL)

    # stage A: sample candidates + verify
    accepted = []
    cand_file = OUT / "candidates.jsonl"
    if cand_file.exists():
        accepted = [json.loads(l) for l in cand_file.read_text().splitlines() if l.strip()]
    else:
        for s in range(0, len(pool), 8):
            chunk = pool[s:s + 8]
            prompts = [PROMPT.format(q=p["question"]) for p in chunk]
            enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to("cuda:0")
            gen = model.generate(**enc, max_new_tokens=512, do_sample=True, temperature=0.7,
                                 top_p=0.95, num_return_sequences=n_per,
                                 pad_token_id=tok.pad_token_id or tok.eos_token_id)
            for j, p in enumerate(chunk):
                cons = None  # lazy: only compute consensus if some candidate exists
                for k in range(n_per):
                    text = tok.decode(gen[j * n_per + k][enc["input_ids"].shape[1]:],
                                      skip_special_tokens=True)
                    accepted.append({"id": p["id"], "question": p["question"],
                                     "answer": p["answer"], "solution": text, "verified": None})
            print(f"[svd] sampled {min(s+8, len(pool))}/{len(pool)}")
        cand_file.write_text("\n".join(json.dumps(r) for r in accepted) + "\n")

    # stage B: verify — group by problem, take consensus answer once, keep matching sols
    if not any(r["verified"] for r in accepted):
        from collections import defaultdict
        by_q = defaultdict(list)
        for r in accepted:
            by_q[r["id"]].append(r)
        n_done = 0
        for qid, rs in by_q.items():
            cons = pot_consensus(model, tok, rs[0]["question"])
            for r in rs:
                r["verified"] = cons is not None and is_correct(r["solution"], str(cons))
            n_done += 1
            if n_done % 50 == 0:
                cand_file.write_text("\n".join(json.dumps(r) for r in accepted) + "\n")
                print(f"[svd] verified {n_done}/{len(by_q)} problems")
        cand_file.write_text("\n".join(json.dumps(r) for r in accepted) + "\n")
    ok = [r for r in accepted if r["verified"]]
    print(f"[svd] accepted {len(ok)}/{len(accepted)} solutions "
          f"(across {len(set(r['id'] for r in ok))} problems)")

    # stage C: SFT on accepted solutions (1 epoch) — target = the model's OWN verified
    # solution text (that's what makes this self-distillation, not gold-SFT)
    train_rows = [{"question": r["question"], "answer": r["solution"]} for r in ok]
    from peft import LoraConfig, get_peft_model
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    stats = train_steps(model, tok, train_rows, lr=2.0e-4, batch=8, accum=4, max_len=1024)
    print(f"[svd] trained on {len(ok)} verified solutions, tokens={stats['tokens']}, "
          f"mean_loss={stats['mean_loss']:.4f}")

    # stage D: held-out eval
    battery = load("probes/battery_held_out.jsonl")[:1000]
    preds = gen_greedy(model, tok, battery, max_new=512, batch=8)
    acc = sum(1 for p in preds
              if is_correct(p["text"], next(b["answer"] for b in battery if b["id"] == p["id"])))
    acc /= len(preds)
    print(f"[svd] HELD-OUT ACC = {acc:.3f}  (Tier-0 static arm reference: 0.103-0.125)")
    (OUT / "svd_result.json").write_text(json.dumps(
        {"held_out_acc": acc, "n_accepted": len(ok), "n_sampled": len(accepted),
         "tokens": stats["tokens"], "mean_loss": stats["mean_loss"], "seed": seed}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-problems", type=int, default=800)
    ap.add_argument("--n-per", type=int, default=8)
    ap.add_argument("--seed", type=int, default=17)
    a = ap.parse_args()
    main(a.n_problems, a.n_per, a.seed)
