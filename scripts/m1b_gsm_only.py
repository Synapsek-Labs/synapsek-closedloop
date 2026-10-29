# Nyx-1 v0 path: GSM8K-only bf16 train + gate.
# 2026-10-29 finding: MATH mixing cannibalizes GSM8K at 1.5B (both 4-bit-trained
# and bf16-trained mixed adapters regressed GSM8K). The honest v0 is the
# domain where the loop demonstrably improves the base model: GSM8K PoT.
# Accept rule (pre-registered): GSM8K delta >= base + 2%, MATH must not
# regress below base - 2% (telemetry domain, tolerance for eval noise).
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
    rows = _rows("work_pot.jsonl")
    print(f"[nyx1-gsm] corpus: {len(rows)} GSM8K PoT pairs (bf16 base)")

    train_student_pot(NODE, rows, out_name="delta_gsm_bf16",
                      replay_ratio=1.0, dtype=DTYPE)
    print("[nyx1-gsm] TRAIN-DONE")

    gsm_tasks = [json.loads(l) for l in
                 (REPO / "probes/battery_held_out.jsonl").read_text().splitlines()
                 if l.strip()][:N_EVAL]
    math_tasks = _rows("battery_math.jsonl")[:N_EVAL]

    tok, base = _fresh()
    gsm_base = eval_pot(base, tok, gsm_tasks, label="nyx-gsm-base")
    del base
    torch.cuda.empty_cache()

    tok, base2 = _fresh()
    wrapped = PeftModel.from_pretrained(base2, str(ndir / "delta_gsm_bf16"))
    wrapped.eval()
    gsm_delta = eval_pot(wrapped, tok, gsm_tasks, label="nyx-gsm-delta")
    del wrapped, base2
    torch.cuda.empty_cache()

    tok, base3 = _fresh()
    math_base = eval_pot(base3, tok, math_tasks, label="nyx-math-base")
    del base3
    torch.cuda.empty_cache()

    tok, base4 = _fresh()
    w2 = PeftModel.from_pretrained(base4, str(ndir / "delta_gsm_bf16"))
    w2.eval()
    math_delta = eval_pot(w2, tok, math_tasks, label="nyx-math-delta")

    gsm_d = gsm_delta - gsm_base
    math_d = math_delta - math_base
    accepted = (gsm_d >= 0.02) and (math_delta >= math_base - 0.02)
    res = {
        "gsm8k": {"base": gsm_base, "delta": gsm_delta},
        "math": {"base": math_base, "delta": math_delta},
        "deltas": {"gsm8k": gsm_d, "math": math_d},
        "accepted": accepted, "margin": 0.02, "math_tolerance": 0.02,
        "n_eval": N_EVAL, "dtype": "bf16", "domains_trained": ["gsm8k"],
        "note": "GSM8K-only adapter; MATH is telemetry-only after mixed-adapter nulls",
    }
    (ndir / "gate_nyx_gsm.json").write_text(json.dumps(res))
    print(f"[nyx1-gsm-gate] {res}")
    print(f"[nyx1-gsm-gate] {'ACCEPT' if accepted else 'REJECT'} "
          f"(gsm8k {gsm_base:.0%}->{gsm_delta:.0%}, math {math_base:.0%}->{math_delta:.0%})")


if __name__ == "__main__":
    main()
