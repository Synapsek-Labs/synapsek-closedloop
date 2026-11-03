# Band-sampling kill-test STEP 2: arm training (pre-registration d8a0ec7).
# LoRA r16 on nyx-2-joint-v3, replay-anchored pair recipe (security_train.py).
# Arms: A = uniform sample, B = learnable band (probe rate 0 < r < 1).
# Same steps: both arms train on the SAME number of pairs, 2 epochs.
# Run on shinobi (spark-venv):
#   spark-venv\Scripts\python.exe scripts\bandsamp_train.py <A|B> <seed 1|2|3>
# Adapter -> runs/node/shinobi-1/bandsamp/<arm>_s<seed>
import json, random, sys, io, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

ARM = sys.argv[1].upper() if len(sys.argv) > 1 else "A"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
assert ARM in ("A", "B")

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
POOL = NODE / "bandsamp_pool.jsonl"
MODEL_DIR = r"C:\Users\User\hf_models\nyx-2-joint-v3"
OUT = NODE / "bandsamp" / f"{ARM}_s{SEED}"
LR = 5e-5
EPOCHS = 2
MAXLEN = 2048
R = 16


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)
    rows = [json.loads(l) for l in
            POOL.read_text(encoding="utf-8").splitlines() if l.strip()]
    band = [r for r in rows if 0.0 < r["rate"] < 1.0]
    n = len(band)
    if ARM == "B":
        sel = band
    else:  # A: uniform sample of the same size from the whole pool
        sel = random.sample(rows, min(n, len(rows)))
    print(f"[bs-{ARM}s{SEED}] pool={len(rows)} band={n} selected={len(sel)}",
          flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    model.eval()
    cfg = LoraConfig(r=R, lora_alpha=2 * R, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=LR)

    # replay-anchored pair extraction from probe rows (prefix + target)
    pairs, skipped = [], 0
    for r in sel:
        msgs = list(r["prefix"]) + [dict(r["target"])]  # target keeps verified tool_calls
        prompt = tok.apply_chat_template(msgs[:-1], tokenize=False,
                                          add_generation_prompt=True)
        full = tok.apply_chat_template(msgs, tokenize=False)
        p = commonprefix([prompt, full])
        if len(p) < len(prompt) - 16:
            skipped += 1
            continue
        tgt = full[len(p):]
        if tgt.strip():
            pairs.append((p, tgt))
    print(f"[bs-{ARM}s{SEED}] {len(pairs)} pairs, {skipped} skipped", flush=True)
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
                print(f"[bs-{ARM}s{SEED}] ep{ep + 1} step {step} "
                      f"loss~{tot / 100:.3f} ({time.time() - t0:.0f}s)",
                      flush=True)
                tot = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT / "tokenizer"))
    print(f"[bs-{ARM}s{SEED}] DONE {step} steps -> {OUT} "
          f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()