# Learning Node MVP — cycle log & verdict — dated 2026-10-28

System built: src/node/nightly.py + src/node/dpo.py (collect -> train delta ->
held-out gate -> exchange sync). Gate pre-registered: accept ONLY if delta
beats base by >= +2% on 60 fresh held-out tasks. Workload: synthetic KB
3-hop agent tasks, one-shot exemplar, execution-verified labels.

## Cycles (node shinobi-1)

| cycle | recipe | verified successes | gate verdict |
|---|---|---|---|
| 1 | 3-hop, temp 0.7, no exemplar | 1/60 (2%) | no delta (min-data gate refused) |
| 2 | 2-hop truncated + exemplar + greedy | 0/60 | no delta — TRUNCATION BUG: 2-hop answers unreachable via lookup precedence |
| 3 | full 3-hop + exemplar + greedy | 16/60 (27%) | SFT: base 30.0% vs delta 15.0% -> REJECT |
| 4 | 150 tasks, 1 epoch, lr 5e-5 | 48/150 (32%) | SFT: base 30.0% vs delta 21.7% -> REJECT |
| 5 | DPO on preference pairs (success + first-mistake depth key) | 29 pairs | DPO: base 30.0% vs delta 23.3% -> REJECT |

Ops lessons: greedy-only collection kills outcome variance (0 preference
pairs — need paired rollouts); DPO pass saturates the CUDA allocator (gate
must run in a fresh process); standalone gate must set the exemplar itself
(one invalid 0.0%/0.0% verdict caught and discarded).

## VERDICT: STOP on naive node-learning (pre-registered)

Four independent confirmations that a 1.5B node training on its own
agent-trajectory data degrades held-out performance:
1. SVD (self-verified distillation): 48.9% < 51.5% base
2. Tier-0c closed-loop synthesis: -1.3%
3. Node self-SFT (2 doses): 30->15%, 30->21.7%
4. Node DPO on zero-judge preference pairs: 30->23.3%

At this scale, self-produced trajectory data narrows the distribution
faster than it teaches the procedure. Small-model agents do not bootstrap
from their own verified rollouts with LoRA-scale updates.

## What the MVP DID validate (ship-able)

1. The verification gate works perfectly: 3/3 harmful deltas rejected,
   0 harmful updates deployed. The gate is the product's safety layer.
2. The self-monitor: loc_cum AUROC 0.994 on exact-label agent
   trajectories; abort+restart saves 59% tokens-per-correct-task
   (docs/longhorizon_demo_result.md).
3. Full nightly-cycle infrastructure runs end-to-end unattended on one
   consumer GPU (~1h/cycle at current sizes).

## Open (next registered attempt, NOT defaults)

- Teacher-gated distillation (Bet C): delta trained on open-weight
  TEACHER rollouts (RunPod burst, ~$5), student trains on teacher-verified
  data instead of its own. This is the one unexplored branch — our own
  negatives all share the confound "student = data source".
- Recovery-trajectory training (DeepSeek alternative #5) remains
  unexplored and is distinct from plain SFT.
