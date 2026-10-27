"""Diagnostic v2: count survivors at each stage of synthesize()."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml, random
from src.cartography import battery
from src.loop.train_arm import load_policy
from src.loop import synthesizer as S

cfg = yaml.safe_load(Path("configs/tier0_stage_a.yaml").read_text())
pool = battery.load(cfg["data"]["probe_pool"])
tok, model = load_policy(cfg["model"]["name"], cfg["model"]["load_in_4bit"])

rng = random.Random(0)
failed = [{"id": f"f{i}", "question": p["question"]} for i, p in
          enumerate(rng.sample(pool, 20))]

# stage 1 replay
prompts = [S.SYNTH_PROMPT.format(q=p["question"]) for p in failed]
sources = [p["id"] for p in failed]
candidates = []
texts = S._gen(model, tok, prompts, 512)
for j, raw in enumerate(texts):
    q = S._clean(raw)
    ok = len(q) > 40 and q.endswith("?") and S.has_numeric_answer(q)
    if ok:
        candidates.append({"question": q, "source": sources[j]})
    if j < 6:
        print(f"[{j}] ok={ok} len={len(q)} :: {q[:160]}")

print(f"\nstage1 candidates: {len(candidates)}/20")

# stage 2 replay on first 4
for s in range(0, min(4, len(candidates)), 4):
    chunk = candidates[s:s + 4]
    pot = [S.POT_PROMPT.format(q=c["question"]) for c in chunk for _ in range(2)]
    codes = S._gen(model, tok, pot, 512)
    for j, c in enumerate(chunk):
        for v in range(2):
            code = S._extract_code(codes[j * 2 + v])
            print(f"\n=== cand {s+j} sample {v}: code_extracted={bool(code)} ===")
            print(codes[j * 2 + v][:300])
            if code:
                import subprocess, tempfile, os
                with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
                    f.write(code); p = f.name
                r = subprocess.run([sys.executable, p], capture_output=True, text=True, timeout=20)
                os.unlink(p)
                print(f"   rc={r.returncode} stdout={r.stdout.strip()[:80]!r} err={r.stderr.strip()[:80]!r}")