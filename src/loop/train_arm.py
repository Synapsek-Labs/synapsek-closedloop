"""Train one arm (static or loop) on an RTX 5090-class GPU via QLoRA.

Both arms use IDENTICAL hyperparameters; only the data slices differ. Token budget is
accounted across cycles so arms stay equal (tier0_plan.md).
"""
from __future__ import annotations
import json, math, random
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup)

PROMPT = "Solve the problem. End with the numeric answer.\n\n{q}\n\nSolution:"


def load_policy(model_name: str, load_in_4bit: bool, dtype=torch.bfloat16):
    from transformers import BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(model_name)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=dtype,
                               bnb_4bit_quant_type="nf4") if load_in_4bit else None
    model = AutoModelForCausalLM.from_pretrained(model_name, quantization_config=quant,
                                                 dtype=dtype, device_map="cuda:0")
    model.config.use_cache = False
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
                      task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                      "gate_proj", "up_proj", "down_proj"])
    return tok, get_peft_model(model, lora)


def make_batch(tok, problems: list[dict], max_len: int, device="cuda:0"):
    """problems: [{question, answer}] -> input_ids/labels tensors (+ true token count)."""
    tok_pad = tok.pad_token_id or tok.eos_token_id
    rows = []
    for p in problems:
        src = PROMPT.format(q=p["question"])
        tgt = " " + p["answer"] + tok.eos_token  # full CoT answer from GSM8K
        ids = tok(src, add_special_tokens=True)["input_ids"]
        labs_full = tok(tgt, add_special_tokens=False)["input_ids"]
        ids, labs = ids + labs_full, [-100] * len(ids) + labs_full
        ids, labs = ids[:max_len], labs[:max_len]
        rows.append((ids, labs))
    L = max(len(r[0]) for r in rows)
    pad = tok.pad_token_id or tok.eos_token_id
    input_ids = torch.full((len(rows), L), pad, dtype=torch.long)
    labels = torch.full((len(rows), L), -100, dtype=torch.long)
    attn = torch.zeros((len(rows), L), dtype=torch.long)
    for i, (ids, labs) in enumerate(rows):
        input_ids[i, :len(ids)] = torch.tensor(ids)
        labels[i, :len(labs)] = torch.tensor(labs)
        attn[i, :len(ids)] = 1
    return input_ids.to(device), labels.to(device), attn.to(device)


def train_steps(model, tok, problems: list[dict], lr: float, batch: int, accum: int,
                max_len: int, log_every: int = 10) -> dict:
    """One pass over `problems` (single epoch). Returns token count + mean loss."""
    model.train()
    opt = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=lr)
    n_batches = math.ceil(len(problems) / batch)
    sched = get_cosine_schedule_with_warmup(opt, min(10, n_batches // 10), n_batches)
    rng = random.Random(0)
    order = list(range(len(problems))); rng.shuffle(order)
    total_tokens, losses = 0, []
    opt.zero_grad(set_to_none=True)
    for i in range(n_batches):
        idx = order[i * batch:(i + 1) * batch]
        input_ids, labels, attn = make_batch(tok, [problems[j] for j in idx], max_len)
        out = model(input_ids=input_ids, attention_mask=attn, labels=labels)
        (out.loss / accum).backward()
        total_tokens += int(attn.sum().item())
        losses.append(out.loss.item())
        if (i + 1) % accum == 0 or i == n_batches - 1:
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        if (i + 1) % log_every == 0:
            print(f"  batch {i+1}/{n_batches} loss={sum(losses[-log_every:])/min(log_every,len(losses)):.4f}")
    return {"tokens": total_tokens, "mean_loss": sum(losses) / max(1, len(losses))}


@torch.no_grad()
def probe(model, tok, problems: list[dict], max_new: int = 512, temperature: float = 0.0,
          batch: int = 8) -> list[dict]:
    """Greedy answers for problems: [{id, question}] -> [{id, text}]"""
    from src.cartography.battery import extract_last_number  # noqa: F401  (import guard)
    model.eval(); results = []
    for s in range(0, len(problems), batch):
        chunk = problems[s:s + batch]
        prompts = [PROMPT.format(q=p["question"]) for p in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to("cuda:0")
        gen = model.generate(**enc, max_new_tokens=max_new,
                             do_sample=temperature > 0, pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j, p in enumerate(chunk):
            text = tok.decode(gen[j][enc["input_ids"].shape[1]:], skip_special_tokens=True)
            results.append({"id": p["id"], "question": p["question"], "text": text})
    return results
