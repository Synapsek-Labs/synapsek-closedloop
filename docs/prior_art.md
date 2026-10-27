# Prior-Art Register — dated 2026-10-27, before any experimental claim

Maintained rule: no external claim ("first", "novel") is made that is not consistent
with this document. Every entry was actually retrieved (arXiv/web), not recalled.

## 1. Failure localization + rollout forking in RL — **OCCUPIED, partly concurrent**

- **ELPO** (arXiv:2602.09598): localizes the *first irrecoverable step* via binary-search
  rollout trees (O(log K) probes), hierarchical advantage attribution, error-localized
  adaptive clipping. This is functionally close to our ForkRL concept, minus the trained
  detection head.
- **Belief-Shift Branching** (arXiv:2609.11061): fork placement via model belief-shift
  probing (black-box probe / logit lens); beats entropy/structural selectors; strong RL
  results on OLMo-3-7B.
- **PivotOPD** (arXiv:2609.40285): pivotal-mistake prevention + recovery distillation in
  multi-turn agents; documents that >50% of failed rollouts contain a pivotal mistake.
- Family context: Tree-GRPO, TreePO, TreeRL, FR3E, ARPO — tree/branching RLVR is an
  active, crowded subfield.

**Residual novelty for us:** a *trained* FMD head as fork selector (cheaper at inference
than probe-based localization; reusable at deployment for live self-monitoring) — an
increment over ELPO/belief-shift, NOT a "first". Position ForkRL as a selector variant
benchmarked against theirs, and as the deployment-side monitor.

## 2. Closed-loop curriculum — **partially occupied**

- **LoopTool** (arXiv:2511.09148): closed-loop data evolution for tool-calling (8B > 32B
  teacher). Post-training, single domain.
- **SPaCe** (arXiv:2508.05015): self-paced bandit curriculum for RFT, up to 100× fewer
  samples. Post-training.
- **Middo** (arXiv:2508.21589): model-informed dynamic data optimization for SFT.
- **Curriculum for pretraining exists but is ordering-only**: arXiv:2506.11300 (systematic
  200-model study), arXiv:2509.25380 (TREC, predictive placement), arXiv:2605.30334
  (STR/SAW ordering). None *synthesize new data in response to measured model failures*
  during pretraining.

**Residual novelty:** closed-loop (diagnose→synthesize→train) at **pretraining scale for
a generalist**, with frontier-derived probe batteries. Narrower than originally claimed;
stake it precisely.

## 3. Verification-gated federated agent learning — **partially occupied, system-level gap remains**

- **STABLE** (arXiv:2510.16089): gated continual learning for LLMs (edit evaluated
  against a budget before acceptance). Single-model, no federation, no agents.
- **SecureGate** (ACL 2026): federated LoRA with privacy dual-adapters. Privacy focus,
  no verification-gated capability updates.
- **Geo-distributed LLM training** (ACM): infrastructure-level federation; not
  trajectory-driven agent learning.

**Residual novelty:** the **system claim** — an agent swarm whose nodes learn nightly
from their own verified trajectories (incl. failure annotation), with verification-gated
federated merging and forgetting checks. No published system does this end-to-end.

## 4. Standing conclusions for Synapsek

1. Our strongest defensible claim is the **integration**: open-weights forensics ->
   closed-loop curriculum -> failure-first data -> learning-node federation, as one
   operating system for small models. Individual mechanisms must be cited as related/
   concurrent work.
2. The Tier-0 experiment remains valid and worth running (loop vs static at pretrain
   scale is still unmeasured in the literature), but its framing must cite SPaCe,
   LoopTool, and the pretraining-curriculum line.
3. FMD/ForkRL: reposition as (a) trained-selector benchmark vs ELPO/belief-shift, and
   (b) the deployment-time self-monitor in the Learning Node — where trained detection
   has an advantage no probe method offers (zero extra inference cost at runtime).
4. Monitor weekly: this landscape changed within the last ~4 months; re-check before
   every external claim.
