# Nyx-2 teacher server (port 8002) — qwen3coder-30b-A3B in 4-bit (bnb).
# Teacher rung of the ladder: generates tool-call trajectories that the
# collector executes and verifies. OpenAI-compatible, non-streaming
# (the collector only uses stream=False).
# Run in the MAIN repo venv (transformers 5.x, bitsandbytes):
#   .venv\Scripts\python.exe scripts\nyx2_teacher_server.py
import json, re, sys, time
from pathlib import Path
from typing import Any, Optional

import torch
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

MODEL_DIR = Path(sys.argv[1] if len(sys.argv) > 1
                 else r"C:\Users\User\hf_models\qwen3coder-30b-normal")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8002
MODEL_ID = "qwen3coder-30b"

app = FastAPI()
_model = None
_tok = None


def _load():
    global _model, _tok
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    _tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    _model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_DIR),
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True),
        device_map="cuda:0")
    _model.eval()
    print("[teacher-server] model loaded (4-bit)", flush=True)


class ChatReq(BaseModel):
    model: str = MODEL_ID
    messages: list[dict[str, Any]]
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 2048
    stream: bool = False
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Any] = None


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL_ID, "object": "model"}]}


# Hermes-style tool call blocks used by Qwen chat templates.
TC_O = "<" + "tool_call>"
TC_C = "</" + "tool_call>"


def _parse_tool_calls(text: str):
    calls = []
    # Find every <tool_call {...} > JSON block.
    pat = re.compile(re.escape(TC_O) + r"\s*(\{.*?\})\s*" + re.escape(TC_C),
                     re.DOTALL)
    for i, m in enumerate(pat.finditer(text)):
        try:
            obj = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        name = obj.get("name", "")
        args = obj.get("arguments", {})
        if isinstance(args, dict):
            args = json.dumps(args)
        calls.append({"id": f"call_{i}", "type": "function",
                      "function": {"name": name, "arguments": args}})
    return calls, pat.sub("", text).strip()


def _render(req: ChatReq):
    msgs = []
    for m in req.messages:
        m = dict(m)
        for tc in m.get("tool_calls") or []:
            args = tc.get("function", {}).get("arguments")
            if isinstance(args, str):
                try:
                    tc["function"]["arguments"] = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    tc["function"]["arguments"] = {"raw": args}
        msgs.append(m)
    prompt = _tok.apply_chat_template(
        msgs, tokenize=False, add_generation_prompt=True,
        tools=req.tools)
    return _tok(prompt, return_tensors="pt").to(_model.device)


@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    ids = _render(req)
    t0 = time.time()
    out = _model.generate(
        **ids,
        max_new_tokens=req.max_tokens,
        do_sample=req.temperature > 0,
        temperature=max(req.temperature, 1e-5),
        top_p=max(req.top_p, 1e-5),
        pad_token_id=_tok.pad_token_id or _tok.eos_token_id)
    text = _tok.decode(out[0][ids["input_ids"].shape[1]:],
                       skip_special_tokens=True)
    calls, clean = _parse_tool_calls(text)
    dt = time.time() - t0
    n_out = out.shape[1] - ids["input_ids"].shape[1]
    print(f"[teacher-server] {n_out} tok in {dt:.1f}s "
          f"({n_out/dt:.1f} tok/s), tool_calls={len(calls)}", flush=True)
    msg = {"role": "assistant", "content": clean if calls else text}
    if calls:
        msg["tool_calls"] = calls
    return {"id": "teacher", "object": "chat.completion",
            "created": int(time.time()), "model": MODEL_ID,
            "choices": [{"index": 0, "message": msg,
                         "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": n_out}}


if __name__ == "__main__":
    _load()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")