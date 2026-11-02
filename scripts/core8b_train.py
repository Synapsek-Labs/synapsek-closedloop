# Core 8B QLoRA trainer: qwen3-8b 4-bit NF4, LoRA r64, packed 4096 blocks, 2 epochs.
# Bars frozen in docs/CORE8B_TARGET_BARS.md BEFORE this run.
import json, math, os, time
from pathlib import Path
import numpy as np
import torch
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                           get_cosine_schedule_with_warmup)
from peft import LoraConfig, get_peft_model

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
DATA = NODE / "core8b_data"
OUT = NODE / "core8b_runs"
OUT.mkdir(exist_ok=True)
BASE = Path(r"C:\Users\User\hf_models") / "qwen3-8b-normal"
SEQ, BS, ACC = 4096, 1, 32
EPOCHS = 2
LR = 1e-4
DEV = "cuda"

train = np.load(DATA / "train_blocks.npy", mmap_mode="r")
val = np.load(DATA / "val_blocks.npy", mmap_mode="r")
N = train.shape[0]
steps_per_epoch = N // (BS * ACC)
print(f"blocks={N} steps/epoch={steps_per_epoch}", flush=True)

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(str(BASE), quantization_config=bnb,
                                              torch_dtype=torch.bfloat16,
                                              device_map={"": 0}, attn_implementation="sdpa")
model.config.use_cache = False
lcfg = LoraConfig(r=64, lora_alpha=128, lora_dropout=0.05, bias="none",
                  task_type="CAUSAL_LM",
                  target_modules=["q_proj","k_proj","v_proj","o_proj",
                                  "gate_proj","up_proj","down_proj"])
model = get_peft_model(model, lcfg)
model.print_trainable_parameters()

p = model.parameters()
optim = torch.optim.AdamW([q for q in p if q.requires_grad], lr=LR,
                           weight_decay=0.01, betas=(0.9, 0.95))
total = steps_per_epoch * EPOCHS
sched = get_cosine_schedule_with_warmup(optim, int(0.02 * total), total)

def val_ppl(model, n=64):
    model.eval(); tot = 0.0; cnt = 0
    with torch.no_grad():
        for i in range(n):
            x = torch.from_numpy(val[i].astype(np.int64)).unsqueeze(0).to(DEV)
            lg = model(x).logits[:, :-1].float()
            y = x[:, 1:]
            ce = torch.nn.functional.cross_entropy(lg.reshape(-1, lg.shape[-1]),
                                                    y.reshape(-1), reduction="sum")
            tot += ce.item(); cnt += y.numel()
    model.train(); return math.exp(tot / cnt)

g = torch.Generator().manual_seed(7)
step = 0; t0 = time.time(); hist = []
for ep in range(EPOCHS):
    order = torch.randperm(N, generator=g).numpy()
    for s in range(steps_per_epoch):
        idx = order[s*BS*ACC:(s+1)*BS*ACC]
        for m in range(ACC):
            micro = np.stack([train[j] for j in idx[m*BS:(m+1)*BS]])
            x = torch.from_numpy(micro.astype(np.int64)).to(DEV)
            lg = model(x).logits[:, :-1]
            y = x[:, 1:]
            V = lg.shape[-1]
            tot = 0.0
            for ci in range(0, lg.shape[1], 1024):
                ce = torch.nn.functional.cross_entropy(
                    lg[:, ci:ci+1024].float().reshape(-1, V),
                    y[:, ci:ci+1024].reshape(-1), reduction="sum")
                tot = tot + ce
            loss = tot / y.numel()
            (loss / ACC).backward()
        torch.nn.utils.clip_grad_norm_([q for q in model.parameters() if q.requires_grad], 1.0)
        optim.step(); sched.step(); optim.zero_grad(set_to_none=True)
        step += 1
        if step % 50 == 0:
            el = time.time() - t0
            tok = step * BS * ACC * SEQ
            print(f"[c8b] ep{ep+1} step {step}/{total} tok={tok/1e6:.0f}M "
                  f"loss={loss.item():.3f} lr={sched.get_last_lr()[0]:.2e} ({el:.0f}s)", flush=True)
            hist.append({"step": step, "loss": float(loss.item())})
        if step % 300 == 0:
            vp = val_ppl(model)
            print(f"[c8b] VAL step {step} ppl={vp:.2f}", flush=True)
            hist[-1]["val_ppl"] = vp
            model.save_pretrained(str(OUT / f"ckpt_step{step}"), safe_serialization=True)

final_ppl = val_ppl(model)
model.save_pretrained(str(OUT / "nyx-core-8b-sft"), safe_serialization=True)
res = {"final_val_ppl": final_ppl, "steps": step, "tokens_B": step*BS*ACC*SEQ/1e9, "hist": hist}
(OUT / "core8b_train_result.json").write_text(json.dumps(res, indent=1))
print("TRAIN DONE", json.dumps({k: res[k] for k in ("final_val_ppl","steps","tokens_B")}), flush=True)