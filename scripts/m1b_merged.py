# M1b: multi-domain merged train + admission gate.
# Trains ONE adapter on GSM8K PoT pairs + MATH pairs (replay-anchored v2 recipe),
# then gates against base on BOTH held-out batteries.
# Pre-registered accept rule: no domain regresses below base, and at least one
# domain gains >= +2% (the gate margin). Anything else = REJECT, logged as null.
import json, sys
from pathlib import Path
sys.path.insert(0, ".")

import torch
from peft import PeftModel

from src.node.nightly import NODE_DIR
from src.node.pot_node import eval_pot, load_model, train_student_pot

REPO = Path(__file__).resolve().parents[1]
NODE = "shinobi-1"
N_EVAL = 100


def _rows(name):
    return [json.loads(l) for l in
            (NODE_DIR / NODE / name).read_text().splitlines() if l.strip()]


def main():
    ndir = NODE_DIR / NODE
    gsm = _rows("work_pot.jsonl")
    math = _rows("train_math.jsonl")
    rows = gsm + math
    print(f"[m1b] merged corpus: {len(gsm)} GSM8K PoT + {len(math)} MATH = {len(rows)}")

    train_student_pot(NODE, rows, out_name="delta_m1b", replay_ratio=1.0)
    print("[m1b] TRAIN-DONE")

    # fresh-process gate on both batteries
    gsm_tasks = [json.loads(l) for l in
                 (REPO / "probes/battery_held_out.jsonl").read_text().splitlines()
                 if l.strip()][:N_EVAL]
    math_tasks = _rows("battery_math.jsonl")[:N_EVAL]

    tok, model = load_model()
    tok.padding_side = "left"
    gsm_base = eval_pot(model, tok, gsm_tasks, label="m1b-gsm-base")
    del model
    torch.cuda.empty_cache()

    tok2, model2 = load_model()
    tok2.padding_side = "left"
    delta_model = PeftModel.from_pretrained(model2, str(ndir / "delta_m1b"))
    delta_model.eval()
    gsm_delta = eval_pot(delta_model, tok2, gsm_tasks, label="m1b-gsm-delta")
    del delta_model, model2
    torch.cuda.empty_cache()

    tok3, model3 = load_model()
    tok3.padding_side = "left"
    math_base = eval_pot(model3, tok3, math_tasks, label="m1b-math-base")
    del model3
    torch.cuda.empty_cache()

    tok4, model4 = load_model()
    tok4.padding_side = "left"
    d2 = PeftModel.from_pretrained(model4, str(ndir / "delta_m1b"))
    d2.eval()
    math_delta = eval_pot(d2, tok4, math_tasks, label="m1b-math-delta")

    deltas = {"gsm8k": gsm_delta - gsm_base, "math": math_delta - math_base}
    accepted = all(d >= 0 for d in deltas.values()) and max(deltas.values()) >= 0.02
    res = {
        "gsm8k": {"base": gsm_base, "delta": gsm_delta},
        "math": {"base": math_base, "delta": math_delta},
        "deltas": deltas, "accepted": accepted, "margin": 0.02,
        "n_eval": N_EVAL, "domains_merged": ["gsm8k", "math"],
    }
    (ndir / "gate_m1b.json").write_text(json.dumps(res))
    print(f"[m1b-gate] {res}")
    print(f"[m1b-gate] {'ACCEPT' if accepted else 'REJECT'} "
          f"(gsm8k {gsm_base:.0%}->{gsm_delta:.0%}, math {math_base:.0%}->{math_delta:.0%})")


if __name__ == "__main__":
    main()
