# Wrapped (never-merge) adapter server: base model + LoRA adapter served
# via PeftModel, no weight merge into the base. Per the merge-destruction
# finding (wrapped +19% vs merged +3%), the wrapped form preserves adapter
# gain. Same wire format/API as spark_server.py.
#   python spark_server_peft.py <base_dir> <adapter_dir> <port>
import sys
from pathlib import Path

BASE_DIR = Path(sys.argv[1])
ADAPTER_DIR = Path(sys.argv[2])
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8009
MODEL_ID = ADAPTER_DIR.name + "-wrapped"

import spark_server as ss

_orig_load = ss._load

def _load_wrapped():
    global _model, _tok
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    ss._tok = AutoTokenizer.from_pretrained(str(BASE_DIR), trust_remote_code=True)
    m = AutoModelForCausalLM.from_pretrained(
        str(BASE_DIR), dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    m = PeftModel.from_pretrained(m, str(ADAPTER_DIR))
    m.eval()
    ss._model = m
    gc = m.generation_config
    for attr in ("top_k", "temperature", "top_p"):
        v = getattr(gc, attr, None)
        if isinstance(v, (int, float)) and v <= 0:
            setattr(gc, attr, None if attr == "top_k" else max(float(v), 1e-5))
    print(f"[spark-server-peft] wrapped model loaded (base={BASE_DIR.name}, "
          f"adapter={ADAPTER_DIR.name})", flush=True)

ss._load = _load_wrapped
ss.MODEL_ID = MODEL_ID

if __name__ == "__main__":
    import uvicorn
    _load_wrapped()
    uvicorn.run(ss.app, host="0.0.0.0", port=PORT, log_level="warning")
