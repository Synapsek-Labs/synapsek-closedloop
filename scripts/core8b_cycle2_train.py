# Core 8B CYCLE-2 trainer — low-LR LoRA PARTIAL (never merged; gates decide).
# Spec: synapsek-internal/research/CYCLE2_CORPUS_SPEC.md C6 (FROZEN):
#   base qwen3-8b-normal (raw), LoRA r32 alpha64 attn+mlp, LR 5e-5, 2 epochs,
#   replay-anchored pairs (prompt=-100 mask), MAXLEN 4096, adapter output ONLY.
# GATES (frozen BEFORE training): beat base 79.8 composite / MT >= 4/16 /
#   audit benign_neg >= 80%. Adapter < base => publish null, never merge.
# Recipe lineage: core8b_train.py (QLoRA 4-bit NF4 + cosine/warmup + ckpts)
#                security_train.py (replay-anchored pairs from messages).
# Run on shinobi: .venv\Scripts\python.exe scripts\core8b_cycle2_train.py
#   PREP_ONLY=1 -> build pairs from corpus, print stats, save, exit (CPU-safe)
#   CYCLE2_SMOKE=N -> 1 epoch, N pairs, verbose (GPU)
#   CYCLE2_RESUME=<ckpt dir> -> weights resume, fresh optimizer, seed-7 order
import json, io, math, os, random, sys, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import torch
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                           BitsAndBytesConfig,
                           get_cosine_schedule_with_warmup)
from peft import LoraConfig, PeftModel, get_peft_model

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
# CYCLE tag: "2" (default) -> cycle-2 corpus/adapter names; "3" -> cycle-3
# (amendment 2026-11-14: capability-preserving mix fam 12/13, same spec C6).
CYCLE = os.environ.get("CORE8B_CYCLE", "2")
CORPUS = NODE / ("work_core8b_cycle%s.jsonl" % CYCLE)
BASE = Path(os.environ.get("CYCLE2_BASE", r"C:\Users\User\hf_models\qwen3-8b-normal"))
OUT = Path(os.environ.get("CYCLE2_OUT", str(NODE / "cycle2_runs")))
PAIRS_FILE = NODE / "cycle2_pairs.jsonl"
LR = float(os.environ.get("CYCLE2_LR", "5e-5"))        # spec C6 (frozen)
EPOCHS = 2
SEED = 7
MAXLEN = 4096
ACC = 8                                               # grad accumulation
SMOKE = int(os.environ.get("CYCLE2_SMOKE", "0"))
PREP_ONLY = os.environ.get("PREP_ONLY", "") == "1"
RESUME = os.environ.get("CYCLE2_RESUME", "")
DEV = "cuda"


def norm(messages):
    """tool_calls arguments str->dict (template needs objects); drop None."""
    out = []
    for m in messages:
        m = dict(m)
        tcs = m.get("tool_calls")
        if tcs is None:
            m.pop("tool_calls", None)
        else:
            for tc in tcs:
                a = tc["function"]["arguments"]
                if isinstance(a, str):
                    try:
                        a = json.loads(a)
                    except json.JSONDecodeError:
                        a = {"raw": a}
                tc["function"]["arguments"] = a
        out.append(m)
    return out


def build_pairs(rows, tok):
    """Replay-anchored pairs: prompt = chat-template prefix (-100 mask),
    target = assistant turn incl. tool_calls + im_end. Template-align via
    commonprefix; skip misaligned (never train on mangled context)."""
    pairs, skipped = [], 0
    for r in rows:
        msgs = norm(r["messages"])
        for i, m in enumerate(msgs):
            if m.get("role") != "assistant":
                continue
            prompt = tok.apply_chat_template(
                msgs[:i], tokenize=False, add_generation_prompt=True)
            full = tok.apply_chat_template(msgs[:i + 1], tokenize=False)
            p = commonprefix([prompt, full])
            if len(p) < len(prompt) - 16:
                skipped += 1
                continue
            target = full[len(p):]
            if target.strip():
                pairs.append({"prompt": p, "target": target,
                              "fam": r.get("fam"), "phases": r.get("phases")})
    return pairs, skipped


def load_corpus():
    if not CORPUS.exists():
        print(f"[c2t] MISSING CORPUS {CORPUS} — never train blind", flush=True)
        sys.exit(2)
    rows = [json.loads(l) for l in
            CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[c2t] corpus: {len(rows)} verified rows", flush=True)
    min_rows = int(os.environ.get("CYCLE2_MIN_ROWS", "50"))
    if len(rows) < min_rows:
        print(f"[c2t] ABORT: <{min_rows} rows (spec B1 target 250-300). "
              f"Refusing to train on thin data.", flush=True)
        sys.exit(2)
    return rows


def main():
    t0 = time.time()
    rows = load_corpus()
    tok = AutoTokenizer.from_pretrained(str(BASE), trust_remote_code=True)

    if PREP_ONLY or not PAIRS_FILE.exists():
        pairs, skipped = build_pairs(rows, tok)
        random.Random(SEED).shuffle(pairs)
        from collections import Counter
        fams = Counter(p["fam"] for p in pairs)
        mt = sum(1 for p in pairs if (p.get("phases") or 1) > 1)
        lens = [len(p["prompt"]) + len(p["target"]) for p in pairs]
        print(f"[c2t] pairs={len(pairs)} skipped={skipped} "
              f"mt_pairs={mt} avg_len={sum(lens)//max(1,len(lens))}ch", flush=True)
        print(f"[c2t] fam histogram: {dict(sorted((str(k),v) for k,v in fams.items()))}", flush=True)
        PAIRS_FILE.write_text("\n".join(json.dumps(p, ensure_ascii=False)
                                       for p in pairs), encoding="utf-8")
        print(f"[c2t] pairs saved -> {PAIRS_FILE.name}", flush=True)
        sample = pairs[0]
        print(f"[c2t] SAMPLE prompt tail: ...{sample['prompt'][-200:]!r}", flush=True)
        print(f"[c2t] SAMPLE target head: {sample['target'][:200]!r}", flush=True)
    if PREP_ONLY:
        print(f"[c2t] PREP_ONLY done in {time.time()-t0:.0f}s", flush=True)
        return

    pairs = [json.loads(l) for l in
             PAIRS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
    if SMOKE:
        pairs = pairs[:SMOKE]
        EPOCHS_NOW = 1
        print(f"[c2t] SMOKE: {SMOKE} pairs, 1 epoch", flush=True)
    else:
        EPOCHS_NOW = EPOCHS

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(BASE), quantization_config=bnb, torch_dtype=torch.bfloat16,
        device_map={"": 0}, attn_implementation="sdpa",
        trust_remote_code=True)
    model.config.use_cache = False
    cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, bias="none",
                     task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    if RESUME:
        model = PeftModel.from_pretrained(model, RESUME, is_trainable=True)
        print(f"[c2t] RESUMED weights from {RESUME}", flush=True)
    else:
        model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    model.train()
    torch.manual_seed(SEED)

    params = [q for q in model.parameters() if q.requires_grad]
    optim = torch.optim.AdamW(params, lr=LR, weight_decay=0.01,
                              betas=(0.9, 0.95))
    total = max(1, (len(pairs) * EPOCHS_NOW) // ACC)
    sched = get_cosine_schedule_with_warmup(optim, max(1, int(0.03 * total)),
                                            total)

    step, t0 = 0, time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    for ep in range(EPOCHS_NOW):
        order = list(range(len(pairs)))
        random.Random(SEED + ep).shuffle(order)
        micro = 0
        for k in order:
            pr, tg = pairs[k]["prompt"], pairs[k]["target"]
            p_ids = tok(pr, return_tensors="pt", truncation=True,
                        max_length=MAXLEN).input_ids
            full = tok(pr + tg, return_tensors="pt", truncation=True,
                       max_length=MAXLEN).input_ids.to(DEV)
            labels = full.clone()
            labels[:, :p_ids.shape[1]] = -100
            out = model(input_ids=full, labels=labels)
            (out.loss / ACC).backward()
            micro += 1
            if micro % ACC == 0:
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                optim.step(); sched.step()
                optim.zero_grad(set_to_none=True)
                step += 1
                if step % 10 == 0 or SMOKE:
                    print(f"[c2t] ep{ep+1} step {step}/{total} "
                          f"loss={out.loss.item():.3f} "
                          f"lr={sched.get_last_lr()[0]:.2e} "
                          f"({time.time()-t0:.0f}s)", flush=True)
                if not SMOKE and step % 300 == 0:
                    model.save_pretrained(str(OUT / f"ckpt_cycle{CYCLE}_step{step}"),
                                          safe_serialization=True)

    name = "smoke_adapter" if SMOKE else f"nyx-core-8b-cycle{CYCLE}-adapter"
    model.save_pretrained(str(OUT / name), safe_serialization=True)
    tok.save_pretrained(str(OUT / name / "tokenizer"))
    print(f"[c2t] DONE {step} opt-steps -> {OUT / name} "
          f"({time.time()-t0:.0f}s) — ADAPTER ONLY, NOT MERGED (spec C6)",
          flush=True)


if __name__ == "__main__":
    main()