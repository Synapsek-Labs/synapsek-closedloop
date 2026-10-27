# SVD Result — dated 2026-10-28

Self-Verified Distillation (arXiv:2605.26132, verified) instantiated on our pipeline:
6400 sampled CoT solutions (8×800 pool problems, temp 0.7), PoT 2-program execution
consensus gate, SFT 1 epoch on the 1507 accepted solutions (450k tokens), frozen
held-out eval.

## Result: NEGATIVE

- accepted 1507/6400 (23.5%), covering only 310/800 problems (39% yielded no
  consensus-verified solution)
- held-out acc **48.9%** vs pristine-base **51.5%** → **−2.6%**
- training loss 0.44 (healthy optimization; the damage is distributional, not fitting)

## Interpretation

Same mode-collapse family as Tier-0c: training on a self-selected solvable subset
narrowed the model. Consistent with the reference paper's own observation that
unfiltered/weaker pipelines can hurt — and their gains used much larger seed sets on
Qwen3-4B. Our 1.5B + 800 problems + 310 covered is far below that regime.

## Consequence

SVD is not a GO at this scale. The self-improvement direction (both synthesis-loop and
SVD variants) is now measured twice at 1.5B and failed both times. Standing conclusion:
**small-model self-improvement via self-generated data does not beat the base at our
scale.** Research compute redirects to the FMD/monitor line, where Phase-0 produced a
validated signal (loc_cum 0.918).
