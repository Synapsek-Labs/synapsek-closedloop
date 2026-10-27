"""FMD Phase-0 helpers: trajectory collection, judge labeling, hidden-state extraction,
linear probes. See docs/fmd_plan.md for the pre-registered decision criteria.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    import numpy as np

JUDGE_PROMPT = """You are reviewing a solution to a math problem for reasoning errors.

Problem:
{q}

Solution steps:
{steps}

Identify the FIRST step that contains a reasoning or arithmetic error.
Reply with exactly one line: "FIRST_ERROR: <step number>" or "FIRST_ERROR: none".
Do not explain."""


def split_steps(text: str) -> list[str]:
    steps = [s.strip() for s in re.split(r"\n+", text) if s.strip()]
    return steps if steps else [text.strip()]


def judge_first_mistake(judge_tok, judge_model, question: str, trace: str,
                        max_new: int = 64) -> int:
    """Return step index (0-based) of first mistake, or -1 if none found."""
    steps = split_steps(trace)
    numbered = "\n".join(f"Step {i+1}: {s}" for i, s in enumerate(steps))
    prompt = JUDGE_PROMPT.format(q=question, steps=numbered)
    enc = judge_tok(prompt, return_tensors="pt").to("cuda:0")
    out = judge_model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                               pad_token_id=judge_tok.pad_token_id or judge_tok.eos_token_id)
    text = judge_tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    m = re.search(r"FIRST_ERROR:\s*(\d+)", text)
    if m:
        k = int(m.group(1))
        return k - 1 if 1 <= k <= len(steps) else -1
    return -1


@torch.no_grad()
def extract_states(model, tok, question: str, trace: str, layers: list[int],
                   device="cuda:0") -> dict:
    """Forward prompt+trace once; return {layer: {('trace',): vec, (step_i,): vec}}.
    States taken at each step's closing newline token + final token."""
    prompt = "Solve the problem. End with the numeric answer.\n\n" + question + "\n\nSolution:"
    full = prompt + " " + trace
    ids = tok(full, return_tensors="pt", truncation=True, max_length=1024).input_ids.to(device)
    # locate step-boundary token positions: token index of each "\n" inside the trace part
    trace_ids = tok(" " + trace, add_special_tokens=False).input_ids
    prompt_len = len(ids[0]) - len(trace_ids)
    nl_positions, step_marks = [], []
    tid = trace_ids
    for i, t in enumerate(tid):
        if tok.decode([t]).strip() == "" and "\n" in tok.decode([t]):
            step_marks.append(prompt_len + i)
    step_marks.append(len(ids[0]) - 1)  # final token for trace-level readout
    out = model(ids, output_hidden_states=True)
    res = {}
    for L in layers:
        h = out.hidden_states[L][0]          # [seq, d]
        res[L] = {i: h[p].float().cpu().numpy() for i, p in enumerate(step_marks)}
    res["n_steps"] = len(step_marks) - 1     # last mark is the trace readout
    return res


def train_probe(X: "np.ndarray", y: "np.ndarray") -> "object":
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(),
                        LogisticRegression(C=0.1, max_iter=2000))
    clf.fit(X, y)
    return clf  # type: ignore[return-value]  # sklearn Pipeline


def auroc(y_true, scores) -> float:
    from sklearn.metrics import roc_auc_score
    import numpy as np
    y_true, scores = np.asarray(y_true), np.asarray(scores)
    if len(set(y_true.tolist())) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, scores))
