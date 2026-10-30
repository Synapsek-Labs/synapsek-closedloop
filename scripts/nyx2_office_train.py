# Nyx-2 office SFT: train Spark-X2.6-1.7B LoRA delta on the 400
# execution-verified teacher trajectories (work_office.jsonl).
# Replay-anchored supervision: each assistant turn is a (prompt, target)
# pair — prompt = chat template prefix WITH tools + generation prompt,
# target = the exact assistant text the template produces (incl. special
# tokens). Prompt tokens masked with -100.
#
# PRE-REGISTERED GATE (decided before training, 2026-10-30):
#   eval = the office battery in scripts/nyx2_base_eval.py, run against the
#   merged delta served at :8001, vs the base audit (office_acc 0.10).
#   ACCEPT iff merged office_acc >= base office_acc + 0.10 (>= 0.20 abs).
#   Control arm = the base audit itself (same eval, same harness).
#
# Run on shinobi (main .venv):
#   .venv\Scripts\python.exe scripts\nyx2_office_train.py
import json, sys, io, random, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
DATA = [NODE / "work_office.jsonl", NODE / "work_office_v2.jsonl"]
MODEL_DIR = r"C:\Users\User\hf_models\spark-x2.6-1.7b"
OUT = NODE / "delta_office"
LR = 5e-5
EPOCHS = 2
SEED = 7
MAXLEN = 2048


def norm(messages):
    """Normalize a trajectory: tool_calls arguments str->dict; drop None."""
    out = []
    for m in messages:
        m = dict(m)
        tcs = m.get("tool_calls")
        if tcs is None:
            m.pop("tool_calls", None)
        else:
            for tc in tcs:
                a = tc["function"]["arguments"]
                tc["function"]["arguments"] = (json.loads(a)
                                               if isinstance(a, str) else a)
        out.append(m)
    return out


def build_pairs(tok, rows):
    """(prompt, target) per assistant turn, replay-anchored."""
    pairs = []
    skipped = 0
    for r in rows:
        msgs = norm(r["messages"])
        tools = r["tools"]
        for i, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            prompt = tok.apply_chat_template(
                msgs[:i], tokenize=False, tools=tools,
                add_generation_prompt=True)
            full = tok.apply_chat_template(
                msgs[:i + 1], tokenize=False, tools=tools)
            # transformers 4.x generation prompt and the full render can
            # differ by a few chars around <|Bot|> — align on the true
            # common character prefix (clean special-token boundary).
            p = commonprefix([prompt, full])
            if len(p) < len(prompt) - 16:
                skipped += 1
                continue
            prompt = p
            target = full[len(prompt):]
            if target.strip():
                pairs.append((prompt, target))
    print(f"[office-train] {len(pairs)} pairs, {skipped} skipped (prefix mismatch)")
    return pairs


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)
    rows = []
    for f in DATA:
        if f.exists():
            rows += [json.loads(l) for l in
                     f.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[office-train] {len(rows)} trajectories", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    model.eval()

    cfg = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=LR)

    pairs = build_pairs(tok, rows)
    print(f"[office-train] {len(pairs)} supervised pairs", flush=True)
    random.shuffle(pairs)

    t0 = time.time()
    step = 0
    for ep in range(EPOCHS):
        tot = 0.0
        for prompt, target in pairs:
            p_ids = tok(prompt, return_tensors="pt", truncation=True,
                        max_length=MAXLEN).input_ids.to("cuda:0")
            full = tok(prompt + target, return_tensors="pt", truncation=True,
                       max_length=MAXLEN).input_ids.to("cuda:0")
            # alignment check: prompt tokens must prefix full tokens
            labels = full.clone()
            labels[:, :p_ids.shape[1]] = -100
            out = model(input_ids=full, labels=labels)
            out.loss.backward()
            opt.step(); opt.zero_grad()
            tot += out.loss.item()
            step += 1
            if step % 50 == 0:
                print(f"[office-train] ep{ep + 1} step {step} "
                      f"loss~{tot / 50:.3f} ({time.time() - t0:.0f}s)",
                      flush=True)
                tot = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT / "tokenizer"))
    print(f"[office-train] DONE {step} steps, delta -> {OUT} "
          f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()