# Tier-0 Final Verdict — dated 2026-10-27

Pre-registered criteria: `docs/tier0_plan.md`. This document closes Stage A.

## Verdict: **STOP** for closed-loop fine-tuning at 1.5B scale (vs static mixture)

## Evidence

| Experiment | Design | Result |
|---|---|---|
| Tier-0b (selection loop) | 4 seeds, battery 1000, equal tokens+FLOPs | pooled delta **−0.05% ± 0.58%**, t=−0.09 → null |
| Tier-0c dose 1 (synthesis loop) | seed 17, per_failed=1, bank 172 | delta **+0.4%** → null |
| Tier-0c dose 4 (synthesis loop) | seed 17, per_failed=4, bank 662 | delta **−1.3%** → negative |

Registered rule: PIVOT = wins only on seen probes or selection-null; STOP = nothing at
equal budget. Both loop variants measured; no dose response in the positive direction
(dose ↑ made it worse). Per the pre-registration, further tuning would be forking-paths
research — not run.

## Mechanism of the Tier-0c negative (honest instrumentation)

Cycle-2 training loss 0.51–0.68 vs static ~0.8: the loop arm's final tokens are spent on
4 near-duplicate variants per failed problem — lower loss, narrower distribution. The
synthesis gate (program-of-thought execution, 2-program agreement) guarantees *answer*
correctness but not *diversity*; per_failed>1 multiplies near-copies.

## What is validated (survives the null)

1. **Failure cartography**: probe subsets identify weak areas reliably (solve-rates
   0.13–0.19, stable across seeds; solve-rate rose within-loop 14%→19%).
2. **The synthesis+verification pipeline**: 662 execution-verified problems generated
   end-to-end with zero human input. The machinery works; it did not buy held-out
   accuracy at this scale.
3. **Pre-registered negative-results methodology**: SHA-locked held-out battery,
   token-matched arms, multi-seed, published nulls.

## Claim hygiene

- The null (closed-loop FT vs static mixture at 1.5B, equal budget) is itself an
  unmeasured-in-literature datapoint; publish it with the mechanism analysis.
- Do NOT generalize to pretraining scale from this result (different regime; the
  pretraining-scale question remains open but is not our current attack vector).
- All external claims must remain consistent with `docs/prior_art.md`.

## Redirect

Compute moves to **Bet 1: First-Mistake Detection (FMD) head** — see
`docs/fmd_plan.md` (design doc). Learning Node federation (Bet 3) unchanged; FMD is
its deployment-time self-monitor component.
