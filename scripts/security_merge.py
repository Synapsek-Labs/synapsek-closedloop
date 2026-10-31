# Nyx-2 security merge: fold delta_sec21 into Spark base (fp32 merge,
# bf16 save) -> hf_models/nyx-2-sec-v0. Run on shinobi (spark-venv):
#   spark-venv\Scripts\python.exe scripts\security_merge.py
import sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = r"C:\Users\User\hf_models\spark-x2.6-1.7b"
DELTA = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\delta_sec21")
OUT = Path(r"C:\Users\User\hf_models\nyx-2-sec-v0")

tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
base_fp32 = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR, dtype=torch.float32, device_map="cuda:0",
    trust_remote_code=True)
merged = PeftModel.from_pretrained(base_fp32, str(DELTA))
merged = merged.merge_and_unload()
merged = merged.to(torch.bfloat16)
merged.eval()

OUT.mkdir(parents=True, exist_ok=True)
merged.save_pretrained(str(OUT))
tok.save_pretrained(str(OUT))
print(f"[sec-merge] merged (fp32-merged, bf16-saved) -> {OUT}")