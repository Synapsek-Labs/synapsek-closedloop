# Long-Horizon Monitor Demo Result — dated 2026-10-28

Testbed: multi-hop lookup agent over a synthetic KB, 600 transcripts (~20 turns each,
12,000 turns), Qwen2.5-1.5B-Instruct, 4.3% solve rate. Every turn has EXACT ground
truth (first deviation from the gold hop path = first mistake; zero judge cost).
Collection via 3 parallel GPU workers (5.4x throughput vs serial).

## Results

- **loc_cum val AUROC 0.994** (layer 20) on per-turn states — the cumulative-error
  signal is far stronger in agentic trajectories than single-pass CoT (0.92/0.82).
- **Abort+restart simulation on 300 held-out tasks:**
  - unmonitored: 4.7% solve, **28,936 tokens per correct task**
  - monitored (τ=0.3): 4.7% solve, **11,770 tokens per correct task** → **59% saved**
  - savings hold across τ=0.3–0.7 (58–59%) with solve rate unchanged.

## Interpretation (honest, per prior_art.md §5)

1. The 2.5x cost-per-correct reduction on long-horizon trajectories is the strongest
   internal validation of the Learning Node self-monitor: the mechanism (train probe
   from verified per-turn labels -> stream states -> abort -> restart) works
   end-to-end and pays for itself where trajectories are long.
2. This is an INTERNAL mechanism validation on a synthetic testbed, NOT a novel claim:
   monitor+abort is published (FailFast 14-20% on SWE-bench, OnTrack ~18%); our
   contribution is (a) exact-label zero-judge training data via the KB testbed,
   (b) the finding that the cumulative signal reaches 0.994 AUROC in agentic
   trajectories, (c) integration into the Learning Node system.
3. Caveats: synthetic KB (not SWE-bench-class tasks); retry cost modeled as mean
   success cost; 1.5B policy at 4.3% solve — absolute numbers are small but the
   RATIO (cost per correct) is the metric our strategy optimizes.

## Consequence for the strategy (docs/strategy_small_compute.md)

Bet A (Learning Node MVP) core mechanism: VALIDATED. Proceed to MVP build:
node = Hebri profile; nightly verified-trajectory learning; weight-delta federation
Mac <-> shinobi; self-monitor wired at deployment.