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
NOTE (re-checked 2026-10-28, components now exist separately):
- **LOCAL** (arXiv:2608.15241): single-GPU runtime for contiguous on-device agent
  learning (adapter versioning + KV-cache co-scheduling). Occupies the node RUNTIME
  layer; no federation, no trajectory verification.
- **CURATOR** (arXiv:2606.25115): budget-curated on-device experience memory with
  provenance-gated PEER sharing (memory-level, frozen weights). Occupies memory-level
  insight sharing; not weight-delta federation.
- Federated LoRA/PEFT infra is crowded: Floe (2602.14302), FedWeave (2607.26618),
  RoboFL (2609.34968), EFFEKT (2608.08138), FedTREK-LM (2603.13264).
- Concept-level overlap: "Federated Analyst Fleets" design blog (shared/personal
  adapter split + DP) — same spirit, no published system/eval.
=> The Learning Node claim must be stated as the INTEGRATION (nightly learning from
verified agent TRAJECTORIES -> verification-gated WEIGHT-delta federation -> deployed
self-monitor), citing LOCAL/CURATOR/Floe as component prior art. Each mechanism must
cite its paper.

## 5. Agent runtime self-monitoring / early abort — **OCCUPIED, hot (checked 2026-10-28)**

- **FailFast-RestartSmart** (arXiv:2608.03222): 0.6B monitor predicts failure from
  observable prefixes; restart raises SWE-bench resolve 66.6→71.8%, saves 14.6–20.4%
  tokens. Directly overlaps our abort+restart demo concept.
- **Doomed from the Start** (arXiv:2607.06503): linear probes on hidden states predict
  eventual task failure from round 1; recall-controlled abort cascade. This is very
  close to our loc_cum monitor — our differentiator vs them must be stated carefully.
- **OnTrack** (arXiv:2610.12375): streaming structural monitoring (optimal transport vs
  reference runs), ~1 ms/step, saves ~18% compute, 83% abort precision.
- **Real-Time Detection and Repair** (arXiv:2608.02464): µs-scale telemetry monitors +
  deterministic verification + rollback repair; 52→73% task success on local agents
  (qwen2.5 7b/3b, llama3.1 8b).
- Context: Self-Healing Orchestrators (2606.01416), FIRE (2609.26048), Semantic
  Early-Stopping (2606.27009), prompt-induced waste studies (2608.01347).

**Residual novelty for Synapsek:** NOT the monitor mechanism itself (occupied, and
published results beat our 1.5% short-CoT prototype by an order of magnitude on their
benchmarks). Open: the SYSTEM integration — on-device Learning Nodes that (a) train
their monitor nightly from their own verified trajectories, (b) federate
verification-gated deltas, (c) self-monitor at deployment with zero extra inference
cost. Also open: first-mistake LOCALIZATION (cumulative 0.92 is ours, but pinpointing
+ abort cascades are published). Claims must cite all five works above.

## 6. Standing conclusions for Synapsek (updated 2026-10-28)

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

## 6. Federated LoRA aggregation (checked 2026-10-28, Learning Node gate)
- FedLoRAGuard (EMNLP 2026): adapter integrity/backdoor verification, not improvement gating.
- FC-MoE (arXiv:2606.15625): conflict-aware MoE federated fine-tuning, gradient consensus.
- iFLoRA (ACL 2026): pipelined error-mitigated LoRA aggregation, matrix-wise freezing.
- Forward Intelligence Grid: commercial promotion gate (held-out completion before serving promotion) — single-org pipeline, not peer federation.
- **Verdict:** aggregation/privacy/integrity = OCCUPIED. NOT occupied: peer nodes exchanging weight deltas derived from execution-verified agent trajectories, gated by receiver-side held-out re-verification. Learning Node MVP builds exactly this.
