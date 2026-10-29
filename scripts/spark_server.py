# Spark-X2.6-1.7B local inference server (port 8001) — sibling of nyx1_server.py.
# trust_remote_code is required for the custom Spark2_5ForCausalLM architecture.
import json, time, sys
from pathlib import Path

import torch
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

MODEL_DIR = Path(sys.argv[1] if len(sys.argv) > 1
                 else r"C:\Users\User\hf_models\spark-x2.6-1.7b")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8001

app = FastAPI()
_model = None
_tok = None


def _load():
    global _model, _tok
    from transformers import AutoModelForCausalLM, AutoTokenizer
    _tok = AutoTokenizer.from_pretrained(str(MODEL_DIR), trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        str(MODEL_DIR), dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    _model.eval()
    gc = _model.generation_config
    for attr in ("top_k", "temperature", "top_p"):
        v = getattr(gc, attr, None)
        if isinstance(v, (int, float)) and v <= 0:
            setattr(gc, attr, None if attr == "top_k" else max(float(v), 1e-5))
    print("[spark-server] model loaded", flush=True)


class ChatMsg(BaseModel):
    role: str
    content: str


class ChatReq(BaseModel):
    model: str = "spark-x2.6-1.7b"
    messages: list[ChatMsg]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False


@app.get("/v1/models")
def models():
    return {"object": "list",
            "data": [{"id": "spark-x2.6-1.7b", "object": "model"}]}


def _gen_kwargs(req: ChatReq):
    return dict(max_new_tokens=req.max_tokens,
                do_sample=req.temperature > 0,
                temperature=max(req.temperature, 1e-5), top_p=0.95,
                top_k=None,  # iFlytek ships top_k=-1 ("disabled"); None = skip warper
                pad_token_id=_tok.pad_token_id or _tok.eos_token_id)


@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    from threading import Thread
    from transformers import TextIteratorStreamer
    prompt = _tok.apply_chat_template(
        [m.model_dump() for m in req.messages], tokenize=False,
        add_generation_prompt=True)
    ids = _tok(prompt, return_tensors="pt").to(_model.device)
    t0 = time.time()

    if req.stream:
        streamer = TextIteratorStreamer(_tok, skip_prompt=True,
                                        skip_special_tokens=True)

        def run():
            _model.generate(**ids, streamer=streamer, **_gen_kwargs(req))
        th = Thread(target=run)
        th.start()

        def sse():
            n_out = 0
            for text in streamer:
                n_out += 1
                chunk = {"id": "spark", "object": "chat.completion.chunk",
                         "created": int(time.time()), "model": "spark-x2.6-1.7b",
                         "choices": [{"index": 0, "delta": {"content": text},
                                      "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
            chunk = {"id": "spark", "object": "chat.completion.chunk",
                     "created": int(time.time()), "model": "spark-x2.6-1.7b",
                     "choices": [{"index": 0, "delta": {},
                                  "finish_reason": "stop"}]}
            yield f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            dt = time.time() - t0
            print(f"[spark-server] stream {n_out} tok in {dt:.1f}s "
                  f"({n_out/dt:.1f} tok/s)", flush=True)
        return StreamingResponse(sse(), media_type="text/event-stream")

    out = _model.generate(**ids, **_gen_kwargs(req))
    text = _tok.decode(out[0][ids["input_ids"].shape[1]:],
                       skip_special_tokens=True)
    dt = time.time() - t0
    n_out = out.shape[1] - ids["input_ids"].shape[1]
    print(f"[spark-server] {n_out} tok in {dt:.1f}s ({n_out/dt:.1f} tok/s)",
          flush=True)
    return {"id": "spark", "object": "chat.completion",
            "created": int(time.time()), "model": "spark-x2.6-1.7b",
            "choices": [{"index": 0, "message": {"role": "assistant",
                                                "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": n_out}}


if __name__ == "__main__":
    _load()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
