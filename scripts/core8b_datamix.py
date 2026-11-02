# Core 8B data mix: sample Nemotron agentic corpora -> qwen3 chat template -> packed tokens.
# Pre-registered bars: docs/CORE8B_TARGET_BARS.md. Output: train blocks of SEQ=4096.
import json, glob, random, sys, time
from pathlib import Path
import numpy as np
from transformers import AutoTokenizer

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
OUT = NODE / "core8b_data"
OUT.mkdir(parents=True, exist_ok=True)
SEQ = 4096
TARGET_TOKENS = 200_000_000
DS = Path(r"C:\Users\User\hf_datasets")

# sources with weights (rows sampled per pass)
SOURCES = [
    (str(DS / "nemotron_sft_agentic_v2" / "data" / "tool_calling.jsonl"), 0.45),
    (str(DS / "nemotron_sft_agentic_v2" / "data" / "interactive_agent.jsonl"), 0.25),
    (str(DS / "nemotron_sft_agentic_v2" / "data" / "search.jsonl"), 0.10),
    (str(DS / "nemotron_agentic_v1" / "data" / "tool_calling.jsonl"), 0.15),
    (str(DS / "nemotron_agentic_v1" / "data" / "interactive_agent.jsonl"), 0.05),
]
tok = AutoTokenizer.from_pretrained(str(Path(r"C:\Users\User\hf_models") / "qwen3-8b"))
print("vocab ok", flush=True)

rng = random.Random(20261102)
blocks = []
cur = []
count_tokens = 0
t0 = time.time()
rows_seen = 0
for path, frac in SOURCES:
    if not Path(path).exists():
        print("MISS", path, flush=True); continue
    # sampling stride: keep ~ this fraction of rows
    keep = max(1, int(1 / max(frac, 1e-4)))
    taken = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i % keep != 0:
                continue
            rows_seen += 1
            try:
                r = json.loads(line)
            except Exception:
                continue
            msgs = r.get("messages") or r.get("conversations") or None
            tools = r.get("tools") or []
            if not msgs:
                continue
            # drop NVIDIA internal fields; keep pure chat
            try:
                text = tok.apply_chat_template(
                    msgs, tools=tools or None, tokenize=False,
                    add_generation_prompt=False)
            except Exception:
                try:
                    text = tok.apply_chat_template(msgs, tokenize=False)
                except Exception:
                    continue
            ids = tok(text, add_special_tokens=False)["input_ids"]
            cur.extend(ids)
            while len(cur) >= SEQ:
                blocks.append(np.array(cur[:SEQ], dtype=np.uint32))
                cur = cur[SEQ:]
            taken += 1
            count_tokens += len(ids)
            if rows_seen % 20_000 < 1:
                el = time.time() - t0
                print(f"[mix] rows={rows_seen} tokens={count_tokens/1e6:.0f}M blocks={len(blocks)} "
                      f"({el:.0f}s)", flush=True)
            if count_tokens >= TARGET_TOKENS:
                break
    print(f"[mix] done src {Path(path).name}: tokens {count_tokens/1e6:.0f}M", flush=True)
    if count_tokens >= TARGET_TOKENS:
        break

arr = np.stack(blocks)
np.save(OUT / "train_blocks.npy", arr)
n = arr.shape[0]
# held-out val = last 256 blocks
np.save(OUT / "val_blocks.npy", arr[-256:])
np.save(OUT / "train_blocks.npy", arr[:-256])
meta = {"blocks": int(arr.shape[0] - 256), "val_blocks": 256, "seq": SEQ,
        "total_tokens": int((arr.shape[0] - 256) * SEQ)}
(OUT / "mix_meta.json").write_text(json.dumps(meta, indent=1))
print("MIX DONE", json.dumps(meta), flush=True)