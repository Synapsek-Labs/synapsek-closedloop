# M1b: multi-domain merged train + admission gate — bf16 iteration.
# Trains ONE adapter on GSM8K PoT pairs + MATH pairs (replay-anchored v2 recipe)
# against the UNQUANTIZED bf16 base, then gates bf16 base vs bf16 base+adapter
# on BOTH held-out batteries. (2026-10-29: 4-bit-trained adapter regressed GSM8K
# when merged to bf16 — training/serve dtype must match.)
# Pre-registered accept rule: no domain regresses below base, and at least one
# domain gains >= +2% (the gate margin). Anything else = REJECT, logged as null.
import json, sys
from pathlib import Path
sys.path.insert(0, ".")

import torch
from peft import PeftModel

from src.node.nightly import NODE_DIR
from src.node.pot_node import _load_student, eval_pot, train_student_pot

REPO = Path(__file__).resolve().parents[1]
NODE = "shinobi-1"
N_EVAL = 100
DTYPE = torch.bfloat16


def _rows(name):
    return [json.loads(l) for l in
            (NODE_DIR / NODE / name).read_text().splitlines() if l.strip()]


def _fresh():
    tok, model = _load_student(DTYPE)
    tok.padding_side = "left"
    return tok, model


def main():
    ndir = NODE_DIR / NODE
    gsm = _rows("work_pot.jsonl")
    math = _rows("train_math.jsonl")
    rows = gsm + math
    print(f"[m1b-bf16] merged corpus: {len(gsm)} GSM8K PoT + {len(math)} MATH = {len(rows)}")

    train_student_pot(NODE, rows, out_name="delta_m1b_bf16",
                      replay_ratio=1.0, dtype=DTYPE)
    print("[m1b-bf16] TRAIN-DONE")

    gsm_tasks = [json.loads(l) for l in
                 (REPO / "probes/battery_held_out.jsonl").read_text().splitlines()
                 if l.strip()][:N_EVAL]
    math_tasks = _rows("battery_math.jsonl")[:N_EVAL]

    tok, base = _fresh()
    gsm_base = eval_pot(base, tok, gsm_tasks, label="m1b-gsm-base")
    del base
    torch.cuda.empty_cache()

    tok, base2 = _fresh()
    wrapped = PeftModel.from_pretrained(base2, str(ndir / "delta_m1b_bf16"))
    wrapped.eval()
    gsm_delta = eval_pot(wrapped, tok, gsm_tasks, label="m1b-gsm-delta")
    del wrapped, base2
    torch.cuda.empty_cache()

    tok, base3 = _fresh()
    math_base = eval_pot(base3, tok, math_tasks, label="m1b-math-base")
    del base3
    torch.cuda.empty_cache()

    tok, base4 = _fresh()
    w2 = PeftModel.from_pretrained(base4, str(ndir / "delta_m1b_bf16"))
    w2.eval()
    math_delta = eval_pot(w2, tok, math_tasks, label="m1b-math-delta")

    deltas = {"gsm8k": gsm_delta - gsm_base, "math": math_delta - math_base}
    accepted = all(d >= 0 for d in deltas.values()) and max(deltas.values()) >= 0.02
    res = {
        "gsm8k": {"base": gsm_base, "delta": gsm_delta},
        "math": {"base": math_base, "delta": math_delta},
        "deltas": deltas, "accepted": accepted, "margin": 0.02,
        "n_eval": N_EVAL, "dtype": "bf16", "domains_merged": ["gsm8k", "math"],
    }
    (ndir / "gate_m1b_bf16.json").write_text(json.dumps(res))
    print(f"[m1b-bf16-gate] {res}")
    print(f"[m1b-bf16-gate] {'ACCEPT' if accepted else 'REJECT'} "
          f"(gsm8k {gsm_base:.0%}->{gsm_delta:.0%}, math {math_base:.0%}->{math_delta:.0%})")


if __name__ == "__main__":
    main()
