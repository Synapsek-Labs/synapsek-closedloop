# Tier-0b Verdict — PIVOT (recorded 2026-10-27)

## Results (1000-problem frozen battery, full 7473-problem pool, Qwen2.5-1.5B QLoRA)

| seed | static acc | loop acc | delta |
|------|-----------|----------|-------|
| 17   | 0.120     | 0.107    | −1.3% |
| 41   | 0.103     | 0.118    | +1.5% |
| 97   | 0.114     | 0.111    | −0.3% |
| 113  | 0.108     | 0.107    | −0.1% |

**Pooled: mean delta −0.05%, SE 0.58%, t = −0.09 (df=3), positive sign in 1/4 seeds.**
Budgets matched (575,168 vs 574,795 mean tokens — <0.1% difference).

## Decision (per pre-registered rule in docs/tier0b_extension.md)

**PIVOT — selection-driven loop is insufficient.** Difficulty-bucketed re-weighting of
an existing pool (70% weak-bucket / 30% refresh) provides no measurable advantage over
a well-constructed static mixture at 1.5B / GSM8K / one-epoch scale.

## What this does and does not mean

Established by this experiment:
- The **cartography works**: probe solve-rates (0.13–0.18) correctly and stably identify
  hard vs easy problems across seeds; the loop selects as designed.
- **Selection alone is a null result.** Re-weighting existing data toward measured
  failures does not improve one-epoch post-training of a small model.

NOT established (and NOT claimed):
- Anything about synthesis-driven loops (untested here).
- Anything about multi-epoch training, larger pools, multi-domain pools, or
  pretraining-scale loops. One epoch on a single-domain pool is the most favorable
  regime for a static mixture (nothing is "revisited", so ordering matters little).

## Next (per registered pivot order)

1. **Synthesis-driven loop** (LoopTool-style): generate NEW training items conditioned
   on measured failure modes, vs the same static control. The hypothesis shifts from
   "which existing data" to "can failure-targeted generation create information the
   pool lacks."
2. If synthesis shows signal → multi-domain pool → pretraining-scale loop.
3. Learning Node program unaffected (uses verified-trajectory deltas, not this loop).

Full logs: runs/ on shinobi (node DESKTOP-UP59RNI); verdict JSONs in results/.