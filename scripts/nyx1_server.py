# Nyx-1 v0 local inference server — minimal OpenAI-compatible chat completions.
# Serves the merged bf16 artifact from shinobi's 5090. Hebri connects via a
# custom model alias (base_url http://<shinobi>:8000/v1).
import json, time
from pathlib import Path

import torch
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

MODEL_DIR = Path(r"C:\Users\User\hf_models\nyx-1-v0")

app = FastAPI()

_model = None
_tok = None


def _load():
    global _model, _tok
    from transformers import AutoModelForCausalLM, AutoTokenizer
    _tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    _model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_DIR), dtype=torch.bfloat16, device_map="cuda:0")
    _model.eval()
    print("[nyx1-server] model loaded", flush=True)


class ChatMsg(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    model: str = "nyx-1-v0"
    messages: list[ChatMsg]
    temperature: float = 0.7
    max_tokens: int = 1024
    stream: bool = False


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": "nyx-1-v0", "object": "model"}]}


@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    prompt = _tok.apply_chat_template(
        [m.model_dump() for m in req.messages], tokenize=False,
        add_generation_prompt=True)
    ids = _tok(prompt, return_tensors="pt").to(_model.device)
    t0 = time.time()
    out = _model.generate(
        **ids, max_new_tokens=req.max_tokens,
        do_sample=req.temperature > 0, temperature=max(req.temperature, 1e-5),
        top_p=0.95, pad_token_id=_tok.pad_token_id or _tok.eos_token_id)
    text = _tok.decode(out[0][ids["input_ids"].shape[1]:],
                       skip_special_tokens=True)
    dt = time.time() - t0
    n_out = out.shape[1] - ids["input_ids"].shape[1]
    print(f"[nyx1-server] {n_out} tok in {dt:.1f}s ({n_out/dt:.1f} tok/s)",
          flush=True)
    return {"id": "nyx1", "object": "chat.completion", "created": int(time.time()),
            "model": "nyx-1-v0",
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                 "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": n_out}}


if __name__ == "__main__":
    _load()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
