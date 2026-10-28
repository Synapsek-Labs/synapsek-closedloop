# Monitor Prototype Result — dated 2026-10-28

Setup: loc_cum probe (layer 15) trained on Phase-0 labels; 500 fresh sampled traces
(43.2% solve); per-step states embedded post-hoc (streaming-equivalent, causal decode);
abort-on-threshold simulated vs unmonitored rollouts.

## Results

| policy | solve kept | tokens/correct | aborts |
|---|---|---|---|
| unmonitored | 43.2% | 646 | — |
| τ=0.4 (best) | 43.0% | **636** | 23/500 |
| τ=0.2 | 41.4% | 638 | 58/500 |
| τ=0.05 | 36.8% | 651 | 131/500 |

Mechanically confirmed: the monitor aborts doomed rollouts early and preserves solve
rate at conservative thresholds. But peak savings are ~1.5% of tokens per correct
solution.

## Honest interpretation

1. The signal ranks post-error steps well (AUROC 0.92) but on single-pass GSM8K CoT
   there is simply little waste to reclaim — wrong runs here are not much longer than
   right ones. The frontier survey's 4×+ waste statistic comes from LONG-HORIZON
   agentic runs (8h+, millions of tokens), not single-pass math.
2. Conclusion: the monitor's economic case must be demonstrated on long-horizon agent
   trajectories (where a doomed run costs hours), or reframed around reliability
   (verification triggering, catch-it-early) rather than token savings.
3. The prototype de-risks the mechanism end-to-end (train monitor → stream states →
   threshold → abort → preserved solve rate). What remains is porting it to an
   agentic harness with long trajectories.

## Next options (registered order)

a. Long-horizon demo: SWE-bench-lite or a multi-step tool-use harness on a 7B model
   (RunPod H100, ~$2.5/hr) where the monitor's savings have room to matter.
b. Monitor quality: trained head (not linear probe), calibration fix, more labels —
   tightens the abort precision/solve-tradeoff curve.
c. PROBE-JS belief-shift validation on the 123 labeled traces (cheap, no labels).