# FMD Phase-0 Verdict — dated 2026-10-28

Pre-registered criteria in `docs/fmd_plan.md`. Data: 500 pristine-base Qwen2.5-1.5B
traces (241 correct / 259 wrong, temp-0.7 sampling), 7B judge labels (first mistake
found in 123/600 wrong traces — judge may be conservative), per-step hidden states
layers 8–24, linear probes, 3 splits.

## Results

| Probe | Best layer | AUROC (mean ± sd) | Threshold |
|---|---|---|---|
| (a) trace correctness | 19 | **0.702 ± 0.022** | ≥0.85 required — FAILED |
| (b) loc cumulative (error has occurred by step k) | 15 | **0.918 ± 0.042** | ≥0.75 required — PASSED |
| (b') loc strict (exactly the first-mistake step) | 14 | **0.726 ± 0.099** | informational |

## Pre-registered verdict: **STOP-FMD-1.5B** (trace 0.702 < 0.85)

The registered GO required BOTH (a) and (b). (a) failed → no trained-FMD-head pipeline
at 1.5B. Registered fallback: belief-shift forking (arXiv:2609.11061 PROBE-JS) as the
localizer if FMD is infeasible at this scale.

## Honest interpretation (no threshold-shopping)

1. The headline positive: **per-step hidden states know when an error has occurred
   (0.918)** — at deployment, steps arrive sequentially, so a cumulative-error monitor
   is directly actionable (trigger verification / branch / restart) WITHOUT needing
   trace-level discrimination or exact first-mistake pinpointing.
2. The trace-level replication failed (0.70 vs the paper's 0.95). Known distribution
   differences: we used SAMPLED (temp 0.7) traces; the paper used greedy; our n=500
   vs their larger sets; our problems are GSM8K vs MATH-500. One controlled
   replication (greedy traces, larger n) is registered below as a debugging step for
   the discrepancy — not a re-roll of the verdict.
3. loc_strict (0.726) confirms the paper's implied difficulty gradient: detecting THAT
   an error occurred is much easier than pinpointing WHICH step was first.

## Registered follow-ups (in priority order)

1. **Trace-level replication probe** (greedy traces, n=1000): resolves whether 0.70 is
   a sampling-noise artifact or a real domain gap. If greedy-trace AUROC ≥0.85, the
   paper's regime transfers and the STOP is a sampling artifact → re-open FMD with
   greedy-time monitors.
2. **Belief-shift forking (PROBE-JS)** on the base model: rank-correlation between
   belief-shift peaks and judge-labeled first mistakes on the SAME 123 labeled traces
   (zero new labeling needed).
3. **Cumulative-error monitor prototype**: the 0.918 signal trained as a small head
   and wired to restart/branch actions in an agent loop — measure wasted-token
   reduction vs no-monitor. This is the Learning Node self-monitor, powered by a
   signal we have ALREADY validated.

## Greedy-trace replication result (2026-10-28, registered follow-up #1 — RESOLVED)

| Probe | sampled traces | greedy traces |
|---|---|---|
| trace correctness | 0.702 ± 0.022 | **0.716 ± 0.018** |
| loc_cum | 0.918 ± 0.042 | 0.817 ± 0.131 (only 30 judge-labeled wrong traces — high variance) |
| loc_strict | 0.726 ± 0.099 | n/a (too few labeled positives) |

**Sampling-noise hypothesis REFUTED**: greedy traces score the same as sampled (~0.71).
The gap to the paper's 0.95 is a genuine domain/setup gap at 1.5B (their regime:
MATH-500-style problems, larger n, different extraction). **STOP-FMD-1.5B is a real
negative, not an artifact.** The cumulative-error signal persists across both regimes
(0.92 sampled / 0.82 greedy-with-few-labels) — it remains the actionable product
signal. Note: judge labeling is the data bottleneck (found first mistakes in only
123/600 sampled and 30/228 greedy wrong traces) — label quality work precedes any
further probe scaling.
