# High-N decisive evaluation: base vs merged Nyx-1 artifact on the FULL batteries.
# Motivation: n=100 PoT evals have ~±5-10pp noise; today's gate deltas (+1, -5, -6)
# were within noise of each other. Decision-grade numbers need n>=300.
import json, sys
from pathlib import Path
sys.path.insert(0, ".")

import torch

from src.node.nightly import NODE_DIR
from src.node.pot_node import _load_student, eval_pot

REPO = Path(__file__).resolve().parents[1]
NODE = "shinobi-1"
DTYPE = torch.bfloat16


def _rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def eval_all(model, tok, label):
    gsm = _rows(REPO / "probes/battery_held_out.jsonl")
    math = _rows(NODE_DIR / NODE / "battery_math.jsonl")
    gsm_acc = eval_pot(model, tok, gsm, label=f"{label}-gsm8k-n{len(gsm)}")
    math_acc = eval_pot(model, tok, math, label=f"{label}-math-n{len(math)}")
    return gsm_acc, math_acc


def main():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from experiments.run_longhorizon_demo import MODEL

    out = {}
    tok, base = _load_student(DTYPE)
    tok.padding_side = "left"
    g, m = eval_all(base, tok, "base")
    out["base_bf16"] = {"gsm8k": g, "math": m}
    print(f"[hi-n] base bf16: gsm8k {g:.1%} (n=400), math {m:.1%} (n=100)", flush=True)
    del base
    torch.cuda.empty_cache()

    # merged Nyx-1 artifact (fp32-merged bf16, built from delta_m1b)
    art = Path(r"C:\Users\User\hf_models\nyx-1-v0")
    tok2 = AutoTokenizer.from_pretrained(str(art))
    nyx = AutoModelForCausalLM.from_pretrained(str(art), dtype=DTYPE,
                                               device_map="cuda:0")
    nyx.eval()
    tok2.padding_side = "left"
    g, m = eval_all(nyx, tok2, "nyx1-merged")
    out["nyx1_merged"] = {"gsm8k": g, "math": m}
    print(f"[hi-n] nyx1 merged: gsm8k {g:.1%} (n=400), math {m:.1%} (n=100)", flush=True)

    out["verdict"] = {
        "gsm8k_delta": out["nyx1_merged"]["gsm8k"] - out["base_bf16"]["gsm8k"],
        "math_delta": out["nyx1_merged"]["math"] - out["base_bf16"]["math"],
    }
    (NODE_DIR / NODE / "hi_n_eval.json").write_text(json.dumps(out))
    print(f"[hi-n] RESULT {json.dumps(out['verdict'])} -> hi_n_eval.json", flush=True)


if __name__ == "__main__":
    main()
