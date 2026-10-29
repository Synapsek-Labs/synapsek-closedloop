# Spark-X2.6-1.7B local inference server (port 8001) with native tool calling.
# trust_remote_code is required for the custom Spark2_5ForCausalLM architecture.
# Tool-call wire format (from chat_template.jinja):
#   <TC>NAME<AK>key</AK><AV>value</AV></TC> where TC=tool_call, AK=arg_key, AV=arg_value.
# Tool results come back as <|Tool|> role messages (handled by the template).
import json, re, time, sys
from pathlib import Path
from typing import Any, Optional

import torch
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

MODEL_DIR = Path(sys.argv[1] if len(sys.argv) > 1
                 else r"C:\Users\User\hf_models\spark-x2.6-1.7b")
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8001

# Wire tokens assembled from parts (kept out of literals above for safety).
TC_O = "<" + "tool_call>"
TC_C = "</" + "tool_call>"
AK_O = "<" + "arg_key>"
AK_C = "</" + "arg_key>"
AV_O = "<" + "arg_value>"
AV_C = "</" + "arg_value>"

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


class ChatReq(BaseModel):
    model: str = "spark-x2.6-1.7b"
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Any] = None


@app.get("/v1/models")
def models():
    return {"object": "list",
            "data": [{"id": "spark-x2.6-1.7b", "object": "model"}]}


def _gen_kwargs(req: ChatReq):
    return dict(max_new_tokens=req.max_tokens,
                do_sample=req.temperature > 0,
                temperature=max(req.temperature, 1e-5), top_p=0.95,
                top_k=None,  # iFlytek ships top_k=-1 ("disabled"); None = skip
                pad_token_id=_tok.pad_token_id or _tok.eos_token_id)


TC_RE = re.compile(
    re.escape(TC_O) + r"\s*(?P<name>[^<\s]+)(?P<args>.*?)" + re.escape(TC_C),
    re.DOTALL)
ARG_RE = re.compile(
    re.escape(AK_O) + r"(.*?)" + re.escape(AK_C) + r"\s*" +
    re.escape(AV_O) + r"(.*?)" + re.escape(AV_C), re.DOTALL)


def _parse_tool_calls(text: str):
    calls = []
    for m in TC_RE.finditer(text):
        args = {}
        for am in ARG_RE.finditer(m.group("args")):
            k, v = am.group(1).strip(), am.group(2).strip()
            try:
                args[k] = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                args[k] = v
        calls.append({"id": f"call_{len(calls)}",
                      "type": "function",
                      "function": {"name": m.group("name").strip(),
                                   "arguments": json.dumps(args)}})
    return calls, TC_RE.sub("", text).strip()


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
    from threading import Thread
    from transformers import TextIteratorStreamer
    ids = _render(req)
    t0 = time.time()

    if req.stream:
        streamer = TextIteratorStreamer(_tok, skip_prompt=True,
                                        skip_special_tokens=True)

        def run():
            _model.generate(**ids, streamer=streamer, **_gen_kwargs(req))
        th = Thread(target=run)
        th.start()

        def sse():
            # Buffer, then emit: tool_calls if the model called a tool,
            # else the full content. Correctness over token-latency since
            # prompt prefill dominates wall time for agent-sized prompts.
            parts = []
            for text in streamer:
                parts.append(text)
            full = "".join(parts)
            n_out = len(parts)
            calls, clean = _parse_tool_calls(full)
            if calls:
                for i, c in enumerate(calls):
                    delta_tc = {"index": i, "id": c["id"], "type": "function",
                                "function": {"name": c["function"]["name"],
                                             "arguments": c["function"]["arguments"]}}
                    chunk = {"id": "spark", "object": "chat.completion.chunk",
                             "created": int(time.time()),
                             "model": "spark-x2.6-1.7b",
                             "choices": [{"index": 0,
                                          "delta": {"role": "assistant",
                                                    "tool_calls": [delta_tc]},
                                          "finish_reason": None}]}
                    yield f"data: {json.dumps(chunk)}\n\n"
                chunk = {"id": "spark", "object": "chat.completion.chunk",
                         "created": int(time.time()),
                         "model": "spark-x2.6-1.7b",
                         "choices": [{"index": 0, "delta": {},
                                      "finish_reason": "tool_calls"}]}
                yield f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            else:
                chunk = {"id": "spark", "object": "chat.completion.chunk",
                         "created": int(time.time()),
                         "model": "spark-x2.6-1.7b",
                         "choices": [{"index": 0,
                                      "delta": {"content": clean or full},
                                      "finish_reason": None}]}
                yield f"data: {json.dumps(chunk)}\n\n"
                chunk = {"id": "spark", "object": "chat.completion.chunk",
                         "created": int(time.time()),
                         "model": "spark-x2.6-1.7b",
                         "choices": [{"index": 0, "delta": {},
                                      "finish_reason": "stop"}]}
                yield f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"
            dt = time.time() - t0
            print(f"[spark-server] stream {n_out} tok in {dt:.1f}s, "
                  f"tool_calls={len(calls)}", flush=True)
        return StreamingResponse(sse(), media_type="text/event-stream")

    out = _model.generate(**ids, **_gen_kwargs(req))
    text = _tok.decode(out[0][ids["input_ids"].shape[1]:],
                       skip_special_tokens=True)
    calls, clean = _parse_tool_calls(text)
    dt = time.time() - t0
    n_out = out.shape[1] - ids["input_ids"].shape[1]
    print(f"[spark-server] {n_out} tok in {dt:.1f}s ({n_out/dt:.1f} tok/s), "
          f"tool_calls={len(calls)}", flush=True)
    msg = {"role": "assistant", "content": clean if calls else text}
    if calls:
        msg["tool_calls"] = calls
    return {"id": "spark", "object": "chat.completion",
            "created": int(time.time()), "model": "spark-x2.6-1.7b",
            "choices": [{"index": 0, "message": msg,
                         "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": ids["input_ids"].shape[1],
                      "completion_tokens": n_out}}


if __name__ == "__main__":
    _load()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
