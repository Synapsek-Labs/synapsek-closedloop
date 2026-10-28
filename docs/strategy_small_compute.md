# Synapsek Small-Compute Strategy — dated 2026-10-28

Directive: big labs win with thousands of GPUs; we win by making few GPUs produce the
same RESULT. The unit of ambition is not model capability — it is **cost per successful
task** (already an emerging industry metric: LiveBench, Terminal-Bench, Arize; but
published as a measurement, not optimized as a system).

## The thesis

**Nobody ships a system whose job is to minimize compute-per-successful-task.**
Big labs optimize capability (accuracy, benchmark rank) and let cost fall out. We
optimize the inverse: hold capability, crush the cost. This is measurable, defensible,
and needs ~2 GPUs — because the levers are SYSTEMS, not FLOPs:

1. **Don't run doomed work** — self-monitor aborts failing trajectories early
   (published savings on agent benchmarks: 14-20%; our loc_cum signal validated).
2. **Don't train on unverified data** — execution-gated data only (our PoT gate).
   Quality-gated small datasets repeatedly beat massive ones (LIMO ~817 samples,
   SPaCe 100× sample-efficiency, LoopTool 8B>32B).
3. **Don't learn alone** — verification-gated weight-delta federation across small
   nodes (our Learning Node; nobody publishes this end-to-end).
4. **Use big models briefly, not always** — open-weight teachers on RunPod (~$2.5/hr)
   generate/verify training data for tiny local students; never frontier APIs (ToS).

North-star metric for everything we ship: **tokens & GPU-minutes per correct answer**,
reported alongside solve rate.

## Three buildable bets (each pre-flighted against the landscape)

| Bet | What big labs do | Our way | Status of white space |
|---|---|---|---|
| **A. Learning Node MVP** | Train one huge model centrally | 2+ small nodes (Mac + shinobi) learn nightly from VERIFIED trajectories, exchange gated weight deltas, self-monitor at deployment | Components exist (LOCAL/CURATOR/Floe); the integration is unpublished |
| **B. Cost-per-correct leaderboard for open small models** | Publish capability leaderboards | Publish a cost-per-SUCCESSFUL-task leaderboard for open ≤7B models with our harness (KB testbed = exact labels, zero judge cost) | Metric exists; a maintained open-model leaderboard does not |
| **C. Teacher-assisted gated distillation** | Full pretraining runs | RunPod burst: big open teacher verifies/generates data → tiny student trained locally; measured against our 51.5% base bar | Partially occupied (SVD paper); execution-gated variant at our scale unmeasured — we measured SELF-distillation fails; TEACHER-gated is different and cheap to test (~$20) |

## What is NOT winnable (do not spend here)

- Frontier capability research, pretraining-scale training, novel RL algorithms,
  any race measured in GPU-months. Our measured nulls prove small-model self-training
  loses; big labs own the scale axis by definition.

## RunPod usage policy (per user directive)

- Quick, bounded experiments only: teacher labeling/verification bursts, 7B-class
  training runs, long-horizon demos needing Linux tooling (ALFWorld etc.).
- Always a pre-registered kill-test ≤$20 first; shinobi (free) is the default;
  RunPod is for the thing shinobi physically cannot do (Linux-only harnesses,
  bigger models, burst throughput).
- Budget guardrail per bet: <$100 before a GO decision.

## Sequencing

1. Long-horizon demo (RUNNING) → validates the self-monitor integration mechanism.
2. Bet A MVP build (the strategic core; everything de-risked by our own experiments).
3. Bet B rides on Bet A's harness (same testbed, different output).
4. Bet C as a $20 RunPod kill-test whenever GPU is idle.