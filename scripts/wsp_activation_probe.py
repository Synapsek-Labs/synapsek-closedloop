# WSP kill-test (amended target, 2026-11-08): localize the SFT capability regression.
# Target changed from simple_java/js (proven CHECKER artifact — both arms emit
# identical CORRECT calls yet score 0; ground_truth parses null on our install)
# to the REAL flaw: SFT -16.6pp vs base (python -18.5, multiple -24, parallel -10).
#
# Probe: forward identical prompts through base + SFT, mean-pool per-layer hidden
# states, save [L, d] activation matrices. Diff -> layers where the regression
# lives. Teacher (open, qwen3coder-30b) then proposes bounded edits THERE.
# Two passes to stay inside 32GB VRAM: --model base, then --model sft.

import argparse, json, sys
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = r"C:\Users\User\hf_models\qwen3-8b-normal"
SFT = r"C:\Users\User\hf_models\nyx-core-8b-sft"
DATA = r"C:\Users\User\gorilla\berkeley-function-call-leaderboard\bfcl_eval\data\BFCL_v4_simple_python.json"
OUT = r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1"

# 6 prompts from the regressed categories' surface (hand-written, same intent
# shape as simple_python/multiple/parallel entries; NOT benchmark rows -> no leakage)
PROBES = [
    "Get the current weather in Tokyo, JP.",
    "Get the stock price of AAPL.",
    "Find flights from SFO to JFK on March 4, one way, 2 adults.",
    "Get weather for San Francisco AND the stock price of MSFT.",
    "Check if user john@example.com is active, and if so, get their last login.",
    "Book a table for 4 at an Italian restaurant in Boston on Friday 7pm, party of 4, under the name Alex.",
]


def load(path):
    tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        path, torch_dtype=torch.bfloat16, trust_remote_code=True,
        device_map="cuda")
    model.eval()
    return tok, model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["base", "sft"], required=True)
    a = ap.parse_args()
    path = BASE if a.model == "base" else SFT
    tok, model = load(path)
    acts = {}
    layers = [m for m in model.modules() if m.__class__.__name__.endswith("DecoderLayer")]
    if not layers:
        layers = [m for m in model.modules() if hasattr(m, "self_attn")]
    print(f"[probe] {len(layers)} layers", flush=True)

    def mk(i):
        def hook(mod, inp, out):
            h = out[0] if isinstance(out, tuple) else out
            acts.setdefault(i, []).append(h.detach().float().mean(dim=1).squeeze().cpu())
        return hook

    hs = [l.register_forward_hook(mk(i)) for i, l in enumerate(layers)]
    with torch.no_grad():
        for p in PROBES:
            ids = tok(p, return_tensors="pt").to("cuda")
            model(**ids, use_cache=False)
            print("[probe]", p[:40], flush=True)
    for h in hs:
        h.remove()
    mat = torch.stack([torch.stack(acts[i]).mean(0) for i in sorted(acts)])
    torch.save({"mat": mat, "n_layers": len(layers)},
               rf"{OUT}\wsp_acts_{a.model}.pt")
    print(f"[probe] saved {a.model}: {tuple(mat.shape)}", flush=True)


if __name__ == "__main__":
    main()