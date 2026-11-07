# SCULPTOR S0 — expert-routing working-set probe (pre-registered idea #5).
# Fires on shinobi 5090 when the BFCL queue clears. $0, reads open weights only.
#
# Method: serve qwen3coder-30b-A3B (MoE, 3B active) one layer-hooked; log
# per-token top-k expert ids + router scores over our frozen battery prompts.
# S0 FROZEN BAR (GENESIS2_INVENTION_REGISTER.md): ALIVE iff <=25% of experts
# cover >=95% of tokens with >=0.6 inter-entry consistency (Jaccard) per
# task family; KILL iff >=60% active or consistency <0.3.
#
# Output: runs/node/shinobi-1/sculptor_s0_routing.jsonl (one row per entry)
#         + sculptor_s0_summary.json (working-set stats per task family).

import json, sys, time, argparse
from pathlib import Path

MODEL = r"C:\Users\User\hf_models\qwen3coder-30b-abliterated"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\sculptor_s0_routing.jsonl")
SUMMARY = OUT.with_suffix(suffix=".summary.json")
TOP_K_LOG = 16          # K3-style sparsity reference; qwen3coder may differ — read from config
MAX_NEW_TOKENS = 128    # routing stats only; we do NOT need full answers for S0

# Task-family probe prompts (frozen 2026-11-08; drawn from our batteries'
# surface forms, NOT benchmark data, so no benchmark leakage into the probe).
PROBES = {
    "code_edit": [
        "def add(a, b):\n    return a + b\n\n# refactor to accept *args and sum them",
        "Write a python function that validates an ipv4 address string.",
        "fix the off-by-one: for i in range(len(items)): process(items[i+1])",
        "convert this sql to sqlalchemy: SELECT id, name FROM users WHERE active=1",
        "add type hints and a docstring: class Stack: def push(self, x): ...",
        "write a regex that matches a yyyy-mm-dd date and validate it",
        "refactor: extract the retry loop into a decorator with backoff",
        "write unit tests (pytest) for a function that parses csv lines",
    ],
    "code_explain": [
        "explain what this does: [x[1] for x in sorted(enumerate(a), key=lambda t: -t[1])]",
        "what is the complexity of merging k sorted lists? explain.",
        "why is this slow: string += char in a loop of 1e6?",
        "explain the difference between optimistic and pessimistic locking.",
        "what does `git rebase --onto` do exactly?",
    ],
    "agent_tool": [
        "call the get_weather tool for Melbourne, AU",  # plain intent forms
        "call the read_file tool with path /tmp/x.log then the search tool for ERROR",
        "call book_meeting with attendees [a, b] and duration 30",
        "call the calculator tool: 17.5% of 2380.44",
    ],
    "office": [
        "summarize this table into a 3-line exec summary (fiscal year 2026 revenue).",
        "write a follow-up email to a late invoice, polite but firm.",
        "convert these bullet notes into a weekly status report.",
    ],
    "security": [
        "review this config for security issues: sshd PermitRootLogin yes PasswordAuthentication yes",
        "explain what CVE-style deserialization bugs look like in java.",
        "which of these ls -la permission bits is risky on /etc/shadow?",
    ],
}


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev = "cuda"
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, trust_remote_code=True,
        device_map=dev)

    moe_layers = [m for m in model.modules() if hasattr(m, "gate")]
    if not moe_layers:
        print("SCULPTOR S0: no MoE gate found — model is dense; ABORT with null")
        SUMMARY.write_text(json.dumps({"status": "no_moe"}))
        return
    top_k = int(getattr(moe_layers[0], "top_k", 0) or TOP_K_LOG)
    n_experts = int(getattr(moe_layers[0], "num_experts",
                             len(getattr(moe_layers[0], "weight", [])) or 0) or 0)
    print(f"[S0] {len(moe_layers)} MoE layers, n_experts={n_experts} top_k={top_k}")

    # Router hook: capture gate outputs (pre-dispatch) per layer per token.
    route_rows = []

    def make_hook(layer_idx):
        def hook(mod, inp, out):
            try:
                logits = mod(inp[0]).float()          # [t, E]
            except Exception:
                return
            ids = logits.topk(min(top_k, logits.shape[-1]), dim=-1).indices
            route_rows.append({"layer": layer_idx, "ids": ids.detach().cpu().tolist()})
        return hook

    handles = [l.gate.register_forward_hook(make_hook(i))
               for i, l in enumerate(moe_layers)]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    f = OUT.open("w", encoding="utf-8")
    t0 = time.time()
    for family, prompts in PROBES.items():
        for pi, p in enumerate(prompts):
            route_rows.clear()
            ids = tok(p, return_tensors="pt").to(dev)
            model.generate(**ids, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
            row = {"family": family, "pi": pi, "layers": route_rows}
            f.write(json.dumps(row) + "\n")
            print(f"[S0] {family}/{pi} tokens-routed, {time.time()-t0:.0f}s",
                  flush=True)
    f.close()
    for h in handles:
        h.remove()

    # ---- Aggregate: working-set coverage + consistency per family ----
    def per_family_stats(rows):
        import collections
        counts = collections.Counter()
        entry_sets = []
        for r in rows:
            s, c = set(), 0
            for lay in r["layers"]:
                for tids in lay["ids"]:
                    s.update(tids); c += 1
            counts.update(s); entry_sets.append(s)
        total_tok_layers = sum(len(lay["ids"]) for r in rows for lay in r["layers"])
        # coverage: smallest expert set covering >=95% of routed (token,layer) mass
        ranked = [e for e, _ in counts.most_common()]
        covered, need = 0, 0.95 * total_tok_layers
        ws = 0
        cum = 0
        for e in ranked:
            cum += counts[e]; ws += 1
            if cum >= need:
                break
        # pairwise Jaccard between entries
        jac = []
        for i in range(len(entry_sets)):
            for j in range(i + 1, len(entry_sets)):
                u = entry_sets[i] | entry_sets[j]
                jac.append(len(entry_sets[i] & entry_sets[j]) / len(u) if u else 1.0)
        mean_jac = sum(jac) / len(jac) if jac else 0.0
        return {"working_set_95": ws, "n_entries": len(rows),
                "consistency_jaccard": round(mean_jac, 3)}

    rows = [json.loads(l) for l in OUT.open(encoding="utf-8")]
    out = {"model": MODEL, "n_experts": n_experts, "top_k": top_k,
           "families": {}}
    for fam in PROBES:
        out["families"][fam] = per_family_stats([r for r in rows
                                                  if r["family"] == fam])
    ws = [v["working_set_95"] for v in out["families"].values()]
    jac = [v["consistency_jaccard"] for v in out["families"].values()]
    out["verdict_inputs"] = {
        "max_working_set_frac": round(max(ws) / max(n_experts, 1), 3) if n_experts else None,
        "min_consistency": min(jac),
        "frozen_bars": {"alive": "ws_frac<=0.25 and consistency>=0.6",
                        "kill": "ws_frac>=0.60 or consistency<0.30"},
    }
    SUMMARY.write_text(json.dumps(out, indent=1))
    print(json.dumps(out["verdict_inputs"], indent=1))
    print("SCULPTOR S0 PROBE COMPLETE — summary at", SUMMARY)


if __name__ == "__main__":
    main()