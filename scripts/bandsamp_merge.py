# Band-sampling kill-test STEP 3: merge adapter into nyx-2-joint-v3.
# fp32 merge, bf16 save (security_merge.py recipe). spark-venv:
#   spark-venv\Scripts\python.exe scripts\bandsamp_merge.py <arm> <seed>
import sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ARM = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
SEED = sys.argv[2] if len(sys.argv) > 2 else "1"
BASE = r"C:\Users\User\hf_models\nyx-2-joint-v3"
ADAPTER = Path(rf"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\bandsamp\{ARM}_s{SEED}")
OUT = Path(rf"C:\Users\User\hf_models\bandsamp_{ARM.lower()}_s{SEED}")

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
base_fp32 = AutoModelForCausalLM.from_pretrained(
    BASE, dtype=torch.float32, device_map="cuda:0", trust_remote_code=True)
merged = PeftModel.from_pretrained(base_fp32, str(ADAPTER))
merged = merged.merge_and_unload()
merged = merged.to(torch.bfloat16)
merged.eval()
OUT.mkdir(parents=True, exist_ok=True)
merged.save_pretrained(str(OUT))
tok.save_pretrained(str(OUT))
print(f"[bs-merge] {ARM}_s{SEED} (fp32-merged, bf16-saved) -> {OUT}")