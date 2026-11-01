# COLIBRI 2 KILL-TEST — task-conditioned expert paging feasibility (vault register
# PRIOR_ART_BIG_MODEL_FEEDING.md, criteria frozen BEFORE this run):
#   GO   : top-25% of (layer,expert) units cover >=90% of routed activations per task
#          class AND task-class top-sets differ (Jaccard overlap <= 0.5)
#   PIVOT : near-uniform expert usage within task classes -> no locality to exploit
#   STOP  : tracing overhead >2x with no sampling fix (not evaluated here; batch-1 hooks)
# Runs on shinobi 5090: qwen3coder-30b-A3B 4-bit, router-gate hooks, 30 prompts/class
# sampled from our REAL banks (work_audit / work_office / work_sec21), 48 tokens gen each.
import os, json, random, time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = r"C:\Users\User\hf_models\qwen3coder-30b-normal"
NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
BANKS = {"audit": "work_audit.jsonl", "office": "work_office.jsonl", "sec": "work_sec21.jsonl"}
N_PROMPTS, MAX_NEW = 30, 48
OUT = NODE / "colibri2_probe_result.json"

def load_bank_prompts(fname):
    rows = [json.loads(l) for l in open(NODE / fname, encoding="utf-8") if l.strip()]
    texts = []
    for r in rows:
        t = ""
        for m in r.get("messages", []):
            if m.get("role") == "user":
                t = m.get("content", ""); break
        if t and len(t) > 40:
            texts.append(t[:1200])
    random.seed(42)
    random.shuffle(texts)
    return texts[:N_PROMPTS]

def main():
    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, torch_dtype=torch.bfloat16, load_in_4bit=True,
        device_map="auto", trust_remote_code=True)
    model.eval()

    n_layers = model.config.num_hidden_layers
    n_experts = getattr(model.config, "num_experts", 128)
    topk = getattr(model.config, "num_experts_per_tok", 8)
    print(f"[c2] layers={n_layers} experts={n_experts} topk={topk}", flush=True)

    ACT = {k: {} for k in BANKS}   # class -> {(layer,expert): count}
    gate_mods = [l.mlp.gate for l in model.model.layers]

    def make_hook(layer_idx):
        def hook(mod, inp, out):
            # out: [B, T, n_experts] router logits
            with torch.no_grad():
                ids = out[0].float().topk(topk, dim=-1).indices  # [T, topk]
                for t in range(ids.shape[0]):
                    for e in ids[t].tolist():
                        ACT["_cur"][(layer_idx, e)] = ACT["_cur"].get((layer_idx, e), 0) + 1
        return hook

    for name, fname in BANKS.items():
        prompts = load_bank_prompts(fname)
        ACT["_cur"] = {}
        hooks = [m.register_forward_hook(make_hook(i)) for i, m in enumerate(gate_mods)]
        t0 = time.time()
        for p in prompts:
            msgs = f"<|im_start|>user\n{p}<|im_end|>\n<|im_start|>assistant\n"
            ids = tok(msgs, return_tensors="pt").to(model.device)
            with torch.no_grad():
                model.generate(**ids, max_new_tokens=MAX_NEW, do_sample=False,
                               pad_token_id=tok.eos_token_id)
        for h in hooks:
            h.remove()
        ACT[name] = dict(ACT["_cur"])
        del ACT["_cur"]
        print(f"[c2] {name}: {sum(ACT[name].values())} activations, "
              f"{len(ACT[name])} unique units, {time.time()-t0:.0f}s", flush=True)

    # ---- analysis ----
    def topk_coverage(counts, frac):
        total = sum(counts.values())
        k = max(1, int(len(counts) * frac))
        top = sorted(counts.values(), reverse=True)[:k]
        return sum(top) / total

    units_total = n_layers * n_experts
    res = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "n_prompts": N_PROMPTS,
           "tokens_new": MAX_NEW, "units_total": units_total}
    top_sets = {}
    for name in BANKS:
        c = ACT[name]
        res[name] = {
            "unique_units_used": len(c),
            "top10pct_cover": round(topk_coverage(c, 0.10), 4),
            "top25pct_cover": round(topk_coverage(c, 0.25), 4),
            "top50pct_cover": round(topk_coverage(c, 0.50), 4),
        }
        k = max(1, int(len(c) * 0.25))
        top_sets[name] = set(sorted(c, key=c.get, reverse=True)[:k])

    names = list(BANKS)
    pairs = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = top_sets[names[i]], top_sets[names[j]]
            jac = len(a & b) / max(1, len(a | b))
            pairs[f"{names[i]}~{names[j]}"] = round(jac, 4)
    res["top25pct_jaccard_pairs"] = pairs

    go_coverage = all(res[n]["top25pct_cover"] >= 0.90 for n in names)
    go_diversity = all(v <= 0.5 for v in pairs.values())
    res["verdict"] = ("GO" if (go_coverage and go_diversity)
                      else ("PIVOT" if not go_coverage else "CONDITIONAL-GO"))
    res["criteria"] = {"top25_cover>=0.90_each": go_coverage,
                       "pairwise_jaccard<=0.5": go_diversity}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1), flush=True)

if __name__ == "__main__":
    main()
