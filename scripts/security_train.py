# Nyx-2 security SFT: train Spark-X2.6-1.7B LoRA delta on the 400
# machine-verified audit/forensic answers (work_sec21.jsonl).
# Same replay-anchored recipe as nyx2_office_train.py (prompt=chat-template
# prefix, target=assistant turn, -100 mask on prompt, commonprefix align).
# PRE-REGISTERED GATE: merged security_eval_v21 battery >= base 58.3% + 0.10
# = 68.3%, AND office eval v2 battery no-regression (>= 0.50), AND security
# v1 battery no-collapse (>= base 83% minus tolerance 0.15 => >= 0.68).
# Run on shinobi (spark-venv, tf 4.57 for Spark remote code):
#   spark-venv\Scripts\python.exe scripts\security_train.py
import json, random, sys, io, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
DATA = NODE / "work_sec21.jsonl"
MODEL_DIR = r"C:\Users\User\hf_models\spark-x2.6-1.7b"
OUT = NODE / "delta_sec21"
LR = 5e-5
EPOCHS = 2
SEED = 7
MAXLEN = 2048


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)
    rows = [json.loads(l) for l in
            DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[sec-train] {len(rows)} verified answers", flush=True)

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

    pairs, skipped = [], 0
    for r in rows:
        msgs = r["messages"]
        for i, m in enumerate(msgs):
            if m["role"] != "assistant":
                continue
            prompt = tok.apply_chat_template(
                msgs[:i], tokenize=False,
                add_generation_prompt=True)
            full = tok.apply_chat_template(msgs[:i + 1], tokenize=False)
            p = commonprefix([prompt, full])
            if len(p) < len(prompt) - 16:
                skipped += 1
                continue
            prompt = p
            target = full[len(prompt):]
            if target.strip():
                pairs.append((prompt, target))
    print(f"[sec-train] {len(pairs)} pairs, {skipped} skipped", flush=True)
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
            labels = full.clone()
            labels[:, :p_ids.shape[1]] = -100
            out = model(input_ids=full, labels=labels)
            out.loss.backward()
            opt.step(); opt.zero_grad()
            tot += out.loss.item()
            step += 1
            if step % 100 == 0:
                print(f"[sec-train] ep{ep + 1} step {step} loss~{tot / 100:.3f} "
                      f"({time.time() - t0:.0f}s)", flush=True)
                tot = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT / "tokenizer"))
    print(f"[sec-train] DONE {step} steps -> {OUT} ({time.time() - t0:.0f}s)",
          flush=True)


if __name__ == "__main__":
    main()