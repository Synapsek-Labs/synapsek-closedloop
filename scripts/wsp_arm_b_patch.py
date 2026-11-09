# WSP Arm B — teacher loop: bounded weight edits to repair the SFT regression.
# Prereg (frozen, WSP_BONSAI_LAUNCH_PREREG.md amendment 2026-11-08):
#   target = SFT capability regression (base 79.8 vs SFT 63.2)
#   localization = layers 34-35 (primary, L35 3x divergence) + 3-5 (secondary)
#   bars: PASS iff python>=90 AND multiple>=85 AND parallel>=88 AND no new regression
#   budget: <=0.05% weights touched, open teacher only (no frontier API)
#
# Design: the regression is OUTPUT-LAYER FORMAT PRESSURE (L35). The cheapest
# bounded edit that can relieve it: INTERPOLATE the SFT's late-block weights
# toward the BASE model's (which we measured healthy at 79.8), a fixed low
# alpha per matrix, late layers only. That is a deterministic, auditable,
# bounded "edit" — the same class of surgery as MIT-WSP but alpha-selected by
# measurement, not an LLM. If alpha>0 recovers capability without breaking
# format, Arm B is alive and we then let the open teacher (qwen3coder-30b)
# propose per-matrix alphas as the fancier variant.

import json, sys, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = r"C:\Users\User\hf_models\qwen3-8b-normal"
SFT = r"C:\Users\hf_models\nyx-core-8b-sft"  # overridden below
OUT = r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1"

EDIT_LAYERS = [35]             # primary (prereg; L35 3x divergence, L34 secondary)
EDIT_LAYERS_SEC = [34, 3, 4, 5]  # secondary — OFF (prereg: bounded first)
ALPHA = 0.35                    # interpolation toward base for selected rows
BUDGET_FRAC = 0.0005            # frozen prereg budget: <=0.05% of weights


def state_dicts():
    print("[arm-b] loading base", flush=True)
    mb = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16,
                                              trust_remote_code=True, device_map="cpu")
    print("[arm-b] loading sft", flush=True)
    ms = AutoModelForCausalLM.from_pretrained(sys.argv[1] if len(sys.argv) > 1 else
                                              r"C:\Users\User\hf_models\nyx-core-8b-sft",
                                              torch_dtype=torch.bfloat16,
                                              trust_remote_code=True, device_map="cpu")
    return mb, ms


def main():
    mb, ms = state_dicts()
    sb, ss = mb.state_dict(), ms.state_dict()
    n_edit = n_total = 0
    budget = None
    for k in ss:
        t = ss[k]
        if not torch.is_floating_point(t):
            continue
        n_total += t.numel()
        if budget is None:
            budget = int(BUDGET_FRAC * n_total)
        lay = None
        for L in EDIT_LAYERS:
            if f".{L}." in k:
                lay = L
        if lay is None:
            continue
        # Row-level selection: only the most-divergent rows of L35, within budget.
        a, b = ss[k].float(), sb[k].float()
        if a.shape != b.shape:
            continue
        # per-row cosine distance between SFT and base
        an = a / a.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        bn = b / b.norm(dim=-1, keepdim=True).clamp_min(1e-6)
        d = 1 - (an * bn).sum(-1)
        # allocate budget evenly across the 11 L35 matrices
        n_rows = a.shape[0]
        take = min(n_rows, max(1, int(round(budget / 11 / max(a.shape[-1], 1)))))
        take_n = int(min(take, d.numel()))
        if take_n < 1:
            continue
        idx = torch.topk(d, take_n).indices
        rows = a.clone()
        rows[idx] = (1 - ALPHA) * a[idx] + ALPHA * b[idx]
        ss[k] = rows.to(ss[k].dtype)
        n_edit += take * a.shape[-1]
        print(f"[arm-b] edited {k} rows={take}/{n_rows} alpha={ALPHA}", flush=True)
    frac = n_edit / max(n_total, 1)
    print(f"[arm-b] weights touched: {n_edit}/{n_total} = {frac:.4%} (budget {BUDGET_FRAC:.2%})", flush=True)
    assert frac <= BUDGET_FRAC * 1.05, "budget blown"
    # save patched model
    ms.load_state_dict(ss)
    out_dir = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\User\hf_models\nyx-core-8b-wsp-patch"
    ms.save_pretrained(out_dir, safe_serialization=True)
    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    tok.save_pretrained(out_dir)
    meta = {"alpha": ALPHA, "edit_layers": EDIT_LAYERS, "frac_weights_touched": frac,
            "base": BASE, "target": "sft-regression-repair", "ts": time.strftime("%Y%m%d-%H%M")}
    json.dump(meta, open(rf"{OUT}\wsp_arm_b_meta.json", "w"), indent=1)
    print("[arm-b] saved:", out_dir, flush=True)


if __name__ == "__main__":
    main()