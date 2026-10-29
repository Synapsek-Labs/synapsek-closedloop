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

    # Merge in FULL PRECISION (fp32), then cast to bf16 on save. The previous
    # attempt merged into the 4-bit-quantized base and re-saved 4-bit —
    # double quantization cost several points on the smoke battery.
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from experiments.run_longhorizon_demo import MODEL
    tok = AutoTokenizer.from_pretrained(MODEL)
    base_fp32 = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.float32, device_map="cuda:0")
    merged = PeftModel.from_pretrained(base_fp32, str(NODE_DIR / NODE / "delta_m1b"))
    merged = merged.merge_and_unload()
    merged = merged.to(torch.bfloat16)
    merged.eval()

    OUT.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT))
    print(f"[m2] merged weights (fp32-merged, bf16-saved) -> {OUT}")
    del merged, base_fp32
    torch.cuda.empty_cache()

    # release smoke: merged artifact vs BASE, identical bf16 serving form.
    tok2 = AutoTokenizer.from_pretrained(str(OUT))
    model2 = AutoModelForCausalLM.from_pretrained(str(OUT), dtype=torch.bfloat16,
                                                  device_map="cuda:0")
    model2.eval()
    tok2.padding_side = "left"

    gsm = _rows(REPO / "probes/battery_held_out.jsonl")[:100]
    math = _rows(NODE_DIR / NODE / "battery_math.jsonl")[:100]
    gsm_acc = eval_pot(model2, tok2, gsm, label="nyx1-gsm8k")
    math_acc = eval_pot(model2, tok2, math, label="nyx1-math")
    del model2
    torch.cuda.empty_cache()

    base_bf16 = AutoModelForCausalLM.from_pretrained(
        MODEL, dtype=torch.bfloat16, device_map="cuda:0")
    base_bf16.eval()
    tok3 = AutoTokenizer.from_pretrained(MODEL)
    tok3.padding_side = "left"
    gsm_base = eval_pot(base_bf16, tok3, gsm, label="base-gsm8k-bf16")
    math_base = eval_pot(base_bf16, tok3, math, label="base-math-bf16")

    deltas = {"gsm8k": gsm_acc - gsm_base, "math": math_acc - math_base}
    ok = all(d >= 0 for d in deltas.values()) and max(deltas.values()) >= 0.02
    verdict = {"gsm8k": {"base": gsm_base, "nyx1": gsm_acc},
               "math": {"base": math_base, "nyx1": math_acc},
               "deltas": deltas, "release_ok": ok, "artifact": str(OUT)}
    (NODE_DIR / NODE / "nyx1_v0_smoke.json").write_text(json.dumps(verdict))
    print(f"[m2] SMOKE {'PASS' if ok else 'FAIL'}: "
          f"gsm8k {gsm_base:.0%}->{gsm_acc:.0%}, math {math_base:.0%}->{math_acc:.0%} "
          f"-> {verdict}")


if __name__ == "__main__":
    main()
