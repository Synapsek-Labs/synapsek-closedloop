"""Synthesis-driven loop: generate NEW training problems conditioned on measured failures.

Hypothesis under test (docs/tier0b_verdict.md pivot #1): failure-targeted generation
creates information the pool lacks, unlike selection/re-weighting (null result).

Quality gate: each synthesized problem is solved 3x by the current policy (temp 0.7);
kept only if >=2/3 generations agree, and the majority answer becomes the label.
This is self-consistency verification — labels are grounded in agreement, not trust.
"""
from __future__ import annotations
import random, re
from collections import Counter

from src.cartography.battery import extract_last_number
from src.loop.train_arm import probe

import torch

SYNTH_PROMPT = (
    "Here is a math word problem:\n\n{q}\n\n"
    "Write ONE new math word problem that tests the same skill but uses different "
    "numbers, names, and context. It must have a single numeric answer. "
    "Output ONLY the new problem text, nothing else."
)


def _clean(text: str) -> str:
    """Strip scaffolding the model may add."""
    text = text.strip()
    text = re.sub(r"^(Problem|New problem)\s*[:\-]\s*", "", text, flags=re.I)
    return text.split("\n\n")[0].strip()


def has_numeric_answer(q: str) -> bool:
    return extract_last_number(q) is not None


def synthesize(model, tok, failed_problems: list[dict], per_failed: int = 1,
               max_new: int = 256, verify_samples: int = 3,
               temperature: float = 0.7) -> list[dict]:
    """failed_problems: [{id, question, solved:False}] -> [{id, question, answer, verified, source}]
    Keeps only problems passing the self-consistency gate."""
    import torch
    device = "cuda:0"
    gen_configs = dict(max_new_tokens=max_new, do_sample=True,
                       temperature=temperature, top_p=0.95,
                       pad_token_id=tok.pad_token_id or tok.eos_token_id)

    # 1) generate candidate problems (batched)
    prompts = []
    meta = []
    for p in failed_problems:
        for k in range(per_failed):
            prompts.append(SYNTH_PROMPT.format(q=p["question"]))
            meta.append(p["id"])
    candidates = []
    B = 8
    for s in range(0, len(prompts), B):
        enc = tok(prompts[s:s + B], return_tensors="pt", padding=True,
                  padding_side="left").to(device)
        out = model.generate(**enc, **gen_configs)
        for j in range(out.shape[0]):
            text = tok.decode(out[j][enc["input_ids"].shape[1]:], skip_special_tokens=True)
            q = _clean(text)
            if len(q) > 40 and has_numeric_answer(q) and q.lower() not in ("", "n/a"):
                candidates.append({"question": q, "source": meta[s + j]})

    # 2) verify: solve each candidate 3x at temp 0.7, require >=2/3 agreement
    verified = []
    Bv = 8
    for s in range(0, len(candidates), Bv):
        chunk = candidates[s:s + Bv]
        rep_prompts = [p["question"] for p in chunk for _ in range(verify_samples)]
        enc = tok([f"Solve the problem. End with the numeric answer.\n\n{q}\n\nSolution:"
                   for q in rep_prompts], return_tensors="pt", padding=True,
                  padding_side="left").to(device)
        out = model.generate(**enc, **gen_configs)
        for j, c in enumerate(chunk):
            answers = []
            for v in range(verify_samples):
                idx = j * verify_samples + v
                text = tok.decode(out[idx][enc["input_ids"].shape[1]:], skip_special_tokens=True)
                a = extract_last_number(text)
                if a is not None:
                    answers.append(round(a, 4))
            if not answers:
                continue
            top, cnt = Counter(answers).most_common(1)[0]
            if cnt >= 2:  # >=2/3 self-consistency
                verified.append({"id": f"synth_{s + j:05d}", "question": c["question"],
                                 "answer": str(top), "verified": True,
                                 "source": c["source"]})
    return verified