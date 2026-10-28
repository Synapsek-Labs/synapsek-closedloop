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

## Addendum: teacher-gated distillation kill-test (2026-10-28, later)
Single-variable A/B: student (1.5B), recipe, workload, gate all identical to
the rejected self-SFT cycle; ONLY the data source changed (Qwen2.5-7B-Instruct
teacher, greedy, same exemplar, same GPU).
- Teacher yield: 41/100 verified successes (41% solve vs student's 27-32%)
- Gate: base 30.0% vs delta 15.0% -> REJECT (WORSE than self-data's 21.7%)
Interpretation: data SOURCE is not the (only) confound. Plausible factors:
teacher trajectories exploit the testbed's permissive success semantics
differently; stylistic mismatch between 7B greedy paths and 1.5B policy
capacity; small-n noise (41 trajectories). Per pre-registration, the next
branch is a 32B teacher (RunPod burst ~$5) BEFORE any final STOP — but the
prior on node-learning producing positive deltas is now low; the monitor +
gate ship remains the validated core.

## Addendum 2: DIAGNOSIS of the teacher-data rejection (2026-10-28)

Question: why did the 7B-teacher delta gate at 15% (worse than self-data)?

Findings (diag_teacher.py, diag_teacher2.py):
1. Teacher "success" trajectories contain mid-chain NOT FOUND wandering
   (e.g. lookup(Goldleaf)->NOT FOUND, lookup("CEO of Vertex")->NOT FOUND
   inside a SUCCESS). The success criterion checks only the final answer,
   so noisy paths pass verification.
2. HARD NUMBER: across 89 verified successes (41 teacher + 48 student),
   ZERO are clean-minimal (no NOT FOUND/junk, length <= hops+1). 100% of
   the SFT data in every cycle taught wandering that happened to end
   correctly. This explains all gate rejections uniformly — self-data
   AND teacher-data fail for the same structural reason.
3. The testbed also admits a role-hop skip (lookup precedence makes
   person->company->city reachable without the role hop), so the gold
   path is only loosely defined.

CONCLUSION: the multi-turn lookup testbed is a poor SFT substrate — its
reward is too gameable and NO clean demonstrations exist to imitate.
This is a WORKLOAD defect, not a teacher defect and not evidence against
teacher-gated distillation per se.

REGISTERED FIX (pre-registered before running): switch the node workload
to single-shot execution-verified tasks (the 662-problem PoT bank from
src/loop/synthesizer.py + SVD machinery). A program-of-thought attempt is
one generation — no multi-turn wandering possible — and verification is
hard execution matching, not a gameable final-answer check. Then retry
teacher-SFT (7B teacher, local, $0) on that substrate. Only if that also
fails the gate does the 32B RunPod teacher (or a STOP) come into play.
