"""Synthesis-driven loop with program-of-thought verification.

Pivot #1 from docs/tier0b_verdict.md: failure-conditioned generation of NEW problems.
Label verification is by EXECUTION (model writes Python, we run it; two independent
programs must agree) — a 1.5B judge is too noisy for self-consistency (observed 0/252
pass rate on shinobi), while execution is near-ground-truth for arithmetic.
"""
from __future__ import annotations
import re
import sys
from collections import Counter
from pathlib import Path

import torch

from src.cartography.battery import extract_last_number

SYNTH_PROMPT = (
    "Write ONE new math word problem that tests the same skill as this one, with "
    "different numbers, names, and context. It must be solvable and have a single "
    "numeric answer.\n\nExample problem:\n{q}\n\n"
    "Output ONLY the new problem statement ending with a question mark. "
    "Do NOT solve it, do NOT explain."
)

POT_PROMPT = (
    "Write a short Python program that solves this problem and prints exactly one "
    "number (the answer).\n\nProblem:\n{q}\n\nOutput ONLY the Python code."
)

_SOLUTION_MARKERS = ("to solve", "let's", "we can", "solution", "step ", "answer:",
                     "first,", "if we", "assume", "denote")


def _clean(text: str) -> str:
    """Strip scaffolding and truncate at solution chatter."""
    text = text.strip()
    text = re.sub(r"^(Problem|New problem)\s*[:\-]*\s*", "", text, flags=re.I)
    text = re.sub(r"\*+", "", text)
    low = text.lower()
    cut = len(text)
    for m in _SOLUTION_MARKERS:
        i = low.find(m)
        if i > 40 and i < cut:          # keep problems that START with these words
            cut = i
    text = text[:cut].strip()
    if not text.endswith("?"):
        qpos = text.rfind("?")
        if qpos > 40:
            text = text[:qpos + 1]
    return text


def has_numeric_answer(q: str) -> bool:
    return extract_last_number(q) is not None


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    lines = [l for l in code.strip().splitlines()
             if not re.match(r"^(sure|here|this|note|i'll|let's)\b", l, re.I)]
    code = "\n".join(lines).strip()
    return code if ("print" in code and len(code) < 2000) else ""


def _gen(model, tok, prompts: list[str], max_new: int, temperature: float = 0.7):
    device = "cuda:0"
    enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to(device)
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=True,
                         temperature=temperature, top_p=0.95,
                         pad_token_id=tok.pad_token_id or tok.eos_token_id)
    return [tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True)
            for o in out]


def synthesize(model, tok, failed_problems: list[dict], per_failed: int = 1,
               max_new: int = 512, python_exe: str | None = None) -> list[dict]:
    """failed_problems: [{id, question, ...}] -> verified [{id, question, answer, source}]

    Two-stage gate:
      1. generation filter: cleaned statement, plausible length, numeric reference
      2. program-of-thought verification: 2 independently generated Python programs
         are EXECUTED; label accepted only if both print the same number.
    """
    import subprocess, tempfile, os

    # --- stage 1: generate + filter candidate problems ---
    prompts = [SYNTH_PROMPT.format(q=p["question"])
               for p in failed_problems for _ in range(per_failed)]
    sources = [p["id"] for p in failed_problems for _ in range(per_failed)]
    candidates = []
    B = 8
    for s in range(0, len(prompts), B):
        texts = _gen(model, tok, prompts[s:s + B], max_new)
        for j, raw in enumerate(texts):
            q = _clean(raw)
            if len(q) > 40 and q.endswith("?") and has_numeric_answer(q):
                candidates.append({"question": q, "source": sources[s + j]})

    # --- stage 2: program-of-thought verification via ONE batch-executor process ---
    all_codes = []
    Bv = 8
    for s in range(0, len(candidates), Bv):
        chunk = candidates[s:s + Bv]
        pot_prompts = [POT_PROMPT.format(q=c["question"]) for c in chunk for _ in range(2)]
        codes = _gen(model, tok, pot_prompts, max_new)
        for j, c in enumerate(chunk):
            for v in range(2):
                code = _extract_code(codes[j * 2 + v])
                if code:
                    all_codes.append({"cand": s + j, "sample": v, "code": code})

    exe = python_exe or sys.executable or "python"
    verified = []
    if all_codes and exe:
        import json as _json, tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            _json.dump(all_codes, f); cin = f.name
        cout = cin + ".out"
        runner = Path(__file__).parent / "pot_runner.py"
        r = subprocess.run([exe, str(runner), cin, cout], capture_output=True,
                           text=True, timeout=600, encoding="utf-8", errors="replace")
        results = {}
        try:
            for item in _json.load(open(cout, encoding="utf-8")):
                results.setdefault(item["cand"], {})[item["sample"]] = item
        except Exception:
            pass
        for c in candidates:
            res = results.get(candidates.index(c), {})
            a0, a1 = res.get(0), res.get(1)
            if a0 and a1 and a0["ok"] and a1["ok"] and a0["number"] == a1["number"]:
                verified.append({"id": f"synth_{len(verified):05d}",
                                 "question": c["question"], "answer": str(a0["number"]),
                                 "verified": "exec", "source": c["source"]})
    return verified