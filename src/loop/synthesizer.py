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


_HANG_PATTERNS = ("input(", "while True", "while 1", "sleep(", "stdin",
                  "readline", "input ()")


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.S)
    code = m.group(1) if m else text
    lines = [l for l in code.strip().splitlines()
             if not re.match(r"^(sure|here|this|note|i'll|let's)\b", l, re.I)]
    code = "\n".join(lines).strip()
    if not ("print" in code and len(code) < 2000):
        return ""
    low = code.lower()
    if any(p in low for p in _HANG_PATTERNS):
        return ""                      # static hang filter: input()/infinite loops etc.
    return code


def _gen(model, tok, prompts: list[str], max_new: int, temperature: float = 0.7,
         batch: int = 32):
    """Batched generation; batch 32 keeps the 5090's decode engine fed (VRAM has room)."""
    device = "cuda:0"
    outs = []
    for s in range(0, len(prompts), batch):
        enc = tok(prompts[s:s + batch], return_tensors="pt", padding=True,
                  padding_side="left").to(device)
        out = model.generate(**enc, max_new_tokens=max_new, do_sample=True,
                             temperature=temperature, top_p=0.95,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        outs.extend(tok.decode(o[enc["input_ids"].shape[1]:], skip_special_tokens=True)
                    for o in out)
    return outs


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
    synth_max_new = min(max_new, 256)      # problem statements never need 512 tokens
    texts = _gen(model, tok, prompts, synth_max_new)
    for j, raw in enumerate(texts):
        q = _clean(raw)
        if len(q) > 40 and q.endswith("?") and has_numeric_answer(q):
            candidates.append({"question": q, "source": sources[j]})

    # --- stage 2: program-of-thought verification via ONE batch-executor process ---
    all_codes = []
    pot_prompts = [POT_PROMPT.format(q=c["question"]) for c in candidates for _ in range(2)]
    pot_sources = [i for i in range(len(candidates)) for _ in range(2)]
    codes = _gen(model, tok, pot_prompts, max_new)
    for j, c in enumerate(candidates):
        for v in range(2):
            code = _extract_code(codes[j * 2 + v])
            if code:
                all_codes.append({"cand": j, "sample": v, "code": code})

    exe = python_exe or sys.executable or "python"
    verified = []
    if all_codes and exe:
        import json as _json, tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            _json.dump(all_codes, f); cin = f.name
        cout = cin + ".out"
        runner = Path(__file__).parent / "pot_runner.py"
        r = None
        try:
            r = subprocess.run([exe, str(runner), cin, cout], capture_output=True,
                               text=True, timeout=900, encoding="utf-8",
                               errors="replace")
            if r.returncode != 0:
                print(f"[synth] pot_runner FAILED rc={r.returncode} "
                      f"stderr={r.stderr[-300:]!r}")
        except subprocess.TimeoutExpired:
            print("[synth] pot_runner timed out; salvaging partial results")
        results = {}
        try:
            lines = open(cout, encoding="utf-8").read().strip().splitlines()
            items = []
            for ln in lines:
                try:
                    items.append(_json.loads(ln))
                except Exception:
                    pass  # tolerate a torn final line from a timeout kill
            for item in items:
                key = item.get("idx", item.get("cand"))
                results.setdefault(key, {})[item.get("sample", 0)] = item
        except Exception as e:
            print(f"[synth] pot_runner results unreadable: {e!r} "
                  f"(n_codes={len(all_codes)})")
        for c in candidates:
            res = results.get(candidates.index(c), {})
            a0, a1 = res.get(0), res.get(1)
            if a0 and a1 and a0["ok"] and a1["ok"] and a0["number"] == a1["number"]:
                verified.append({"id": f"synth_{len(verified):05d}",
                                 "question": c["question"], "answer": str(a0["number"]),
                                 "verified": "exec", "source": c["source"]})
    return verified