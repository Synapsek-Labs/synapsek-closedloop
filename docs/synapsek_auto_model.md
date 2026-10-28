# Synapsek Auto — our own model family (plan, 2026-10-29)

## The honest physics

- PRETRAINING from scratch: 1.5B Chinchilla-optimal ≈ 30B tokens ≈
  2.7e20 FLOPs ≈ 500+ GPU-hours on a 5090 (3+ weeks nonstop) or
  ~$1k+ of H100. NOT viable for us, and unnecessary (see below).
- What IS viable and is the entire game: **distill + adapt open bases
  with our verified-data recipe.** Qwen2.5/3 bases are Apache-2.0:
  legally we can fine-tune, rebrand, and distribute with attribution.
  Our replay-anchored + execution-verified + bank-admission stack is
  exactly the machinery for turning a generic open base into a
  Synapsek model.

## The family (target)

| Model | Base | Role |
|---|---|---|
| Synapsek Auto 0.5B | Qwen2.5-0.5B | colibri / laptop CPU |
| Synapsek Auto 1.5B | Qwen2.5-1.5B (Apache-2.0) | default Hebri node |
| Synapsek Auto 3B | Qwen2.5-3B / Qwen3-4B | prosumer GPU |
| Synapsek Auto 8B | Qwen3-8B | 5090-class nodes |

"Super compressed": ship 4-bit (works now — our whole stack runs
4-bit) + optional merged bf16 releases. "Super capable": the swarm
recipe + multi-domain verified data + bank, not magic.

## Registered phases (pre-registered gates, shinobi-first, $0)

- **M1 (multi-domain transfer, also the science replication):** add a
  SECOND execution-verifiable domain (SVAMP/MATH-easy word problems,
  same executor, different distribution). Collect 400, replay-train,
  full-battery admission on shinobi. Gate: adapter > base on the
  second domain battery. PASS = the recipe is general, and the data
  becomes the first multi-domain Synapsek corpus.
- **M2 (Synapsek Auto 1.5B v0):** merge the admitted M1+PoT adapters
  into a RELEASE artifact evaluated on the merged battery + report.
  This is the first model we can call ours (fine-tuned, tested,
  attributed). Gate: >= base on every domain, +2% on at least one.
- **M3 (richer teachers):** open-weight 32B teacher (pod burst, ~$5)
  for higher-yield, more diverse programs; 27B-class teachers on user
  GPUs via the swarm. License-clean only (no API-teacher data).
- **M4 (compression):** 4-bit ship is already proven; optional:
  pruning/distillation pass IF a customer case demands smaller.

## Teacher strategy (2026-10-29, user direction): best open Chinese model as the well

The existence proof: DeepSeek-R1-Distill-Qwen-1.5B was built by
distilling a frontier open model into the SAME Qwen 1.5B base we use —
and it beat much larger models on math benchmarks. Distillation of a
frontier-adjacent open teacher into small bases is exactly how
"small but top" is made.

- Teacher ladder (license-clean, open weights only, never API):
  Qwen2.5-7B (current, shinobi) -> Qwen3-32B / R1-Distill-Qwen-32B
  (pod ~$5 burst) -> biggest open model that fits burst budgets
  (R1-0528 / Qwen3-235B-class via multi-GPU pods when a domain
  warrants it).
- Trust/"obliterate the phone-home" concern: model WEIGHTS are inert
  data — server connections come from app/serving code, not tensors.
  Our stack is fully local (transformers/vLLM on the user's own
  machine); we audit the serving path, ship no telemetry, and every
  SWAP artifact carries provenance so receivers know exactly what
  they adopted. Synapsek Auto = open Chinese excellence, cleaned,
  verified, and improved by the swarm.
- Honest ceiling: distillation makes small models frontier-CALIBER on
  the verified domains we train (math/code/structured tasks); it does
  not make a 1.5B equal a frontier model on open-ended general chat.
  Our pitch is capability-per-watt + trust + self-improvement, not
  raw scale.

## What makes it "first AI" quality

The moat is not weights — it is (1) the verified-data flywheel
(execution gating means zero label noise), (2) the monitor (knows
when it does not know), (3) the bank (cannot be corrupted by its own
learning), (4) the swarm (learns from every other node nightly).
A 1.5B with that system layer beats a raw 1.5B and costs nothing to
run. That is Synapsek's thesis, now demonstrated end to end.
