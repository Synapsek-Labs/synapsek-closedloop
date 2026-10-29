# M2: Nyx-1 v0 release build.
# Merges the gate-ACCEPTED delta_m1b adapter into the base Qwen2.5-1.5B student,
# saves the merged weights (outside the repo, never committed), and runs the
# release smoke battery: GSM8K held-out + MATH held-out, PoT solve rate.
import json, sys
from pathlib import Path
sys.path.insert(0, ".")

import torch
from peft import PeftModel

from src.node.nightly import NODE_DIR
from src.node.pot_node import eval_pot, load_model

NODE = "shinobi-1"
REPO = Path(__file__).resolve().parents[1]
OUT = Path(r"C:\Users\User\hf_models\nyx-1-v0")  # merged model destination (outside repo)


def _rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def main():
    gate = json.loads((NODE_DIR / NODE / "gate_m1b.json").read_text())
    if not gate["accepted"]:
        print(f"[m2] ABORT: gate_m1b not accepted ({gate})")
        sys.exit(1)
    print(f"[m2] building Nyx-1 v0 from accepted delta_m1b (gate: {gate['deltas']})")

    tok, model = load_model()
    merged = PeftModel.from_pretrained(model, str(NODE_DIR / NODE / "delta_m1b"))
    merged = merged.merge_and_unload()
    merged.eval()

    OUT.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT))
    print(f"[m2] merged weights saved to {OUT}")

    # release smoke: re-load merged from disk (proves the artifact is complete)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok2 = AutoTokenizer.from_pretrained(str(OUT))
    model2 = AutoModelForCausalLM.from_pretrained(str(OUT), torch_dtype=torch.bfloat16,
                                                  device_map="cuda:0")
    model2.eval()
    tok2.padding_side = "left"

    gsm = _rows(REPO / "probes/battery_held_out.jsonl")[:100]
    math = _rows(NODE_DIR / NODE / "battery_math.jsonl")[:100]
    gsm_acc = eval_pot(model2, tok2, gsm, label="nyx1-gsm8k")
    math_acc = eval_pot(model2, tok2, math, label="nyx1-math")

    ok = (gsm_acc >= gate["gsm8k"]["delta"] - 0.02) and \
         (math_acc >= gate["math"]["delta"] - 0.02)
    verdict = {"gsm8k": gsm_acc, "math": math_acc,
               "gate_ref": gate["deltas"], "release_ok": ok,
               "artifact": str(OUT)}
    (NODE_DIR / NODE / "nyx1_v0_smoke.json").write_text(json.dumps(verdict))
    print(f"[m2] SMOKE {'PASS' if ok else 'FAIL'}: gsm8k {gsm_acc:.0%}, "
          f"math {math_acc:.0%} -> {verdict}")


if __name__ == "__main__":
    main()
