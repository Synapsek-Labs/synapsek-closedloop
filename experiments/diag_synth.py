"""Diagnostic: what does the synth generator produce, and why does the gate reject?"""
from __future__ import annotations
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cartography import battery
from src.loop.train_arm import load_policy
from src.loop.synthesizer import SYNTH_PROMPT, _clean, has_numeric_answer
from src.loop.probe_runner import run_battery
import yaml, random, torch

cfg = yaml.safe_load(Path("configs/tier0_stage_a.yaml").read_text())
held = battery.load(cfg["data"]["held_out_battery"])
pool = battery.load(cfg["data"]["probe_pool"])
tok, model = load_policy(cfg["model"]["name"], cfg["model"]["load_in_4bit"])

# take 5 failed problems (model fails at ~16% so probe a few)
rng = random.Random(0)
sub = rng.sample(pool, 30)
scored = run_battery(model, tok, sub, max_new=256)
failed = [{"id": r["id"], "question": r["question"]} for r in scored if not r["solved"]][:5]
print(f"failed problems: {len(failed)}")

gen_cfg = dict(max_new_tokens=256, do_sample=True, temperature=0.7, top_p=0.95,
               pad_token_id=tok.pad_token_id or tok.eos_token_id)
prompts = [SYNTH_PROMPT.format(q=p["question"]) for p in failed]
enc = tok(prompts, return_tensors="pt", padding=True, padding_side="left").to("cuda:0")
out = model.generate(**enc, **gen_cfg)
for j, p in enumerate(failed):
    raw = tok.decode(out[j][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    q = _clean(raw)
    print(f"\n--- candidate {j} (clean_ok={len(q)>40}, numeric={has_numeric_answer(q)}) ---")
    print("RAW:", raw[:400].replace("\n", " | "))
    print("CLEAN:", q[:300])