# EVDGT merge: adapter + nyx-2-joint-v3 -> merged bf16 model (security_merge.py recipe).
# python scripts\evdgt_merge.py <U|D> <seed>
import sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ARM = sys.argv[1].upper()
SEED = int(sys.argv[2])
REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
BASE = r"C:\Users\User\hf_models\nyx-2-joint-v3"
ADP = NODE / "evdgt" / f"{ARM}_s{SEED}"
OUT = Path(rf"C:\Users\User\hf_models") / f"evdgt_{ARM}_s{SEED}"

model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.float32,
                                             trust_remote_code=True)
model = PeftModel.from_pretrained(model, str(ADP))
model = model.merge_and_unload()
model = model.to(torch.bfloat16)
model.save_pretrained(str(OUT))
AutoTokenizer.from_pretrained(BASE, trust_remote_code=True).save_pretrained(str(OUT))
print(f"[ev-merge] {ARM}_s{SEED} (fp32-merged, bf16-saved) -> {OUT}", flush=True)
