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

## What makes it "first AI" quality

The moat is not weights — it is (1) the verified-data flywheel
(execution gating means zero label noise), (2) the monitor (knows
when it does not know), (3) the bank (cannot be corrupted by its own
learning), (4) the swarm (learns from every other node nightly).
A 1.5B with that system layer beats a raw 1.5B and costs nothing to
run. That is Synapsek's thesis, now demonstrated end to end.
