# FMD Plan — First-Mistake Detection head — dated 2026-10-28

Top-ranked bet from the frontier survey. Gated: Phase 0 is a cheap kill-test before
any pipeline investment. Companion reading: `docs/prior_art.md` (ELPO/belief-shift/
PivotOPD occupy forking-RL; our wedge is the trained head as a DEPLOYMENT-TIME monitor),
`docs/tier0_verdict_final.md` (Stage A closed).

## Design constraint (from arXiv:2605.09502, verified 2026-10-28)

Linear probes on hidden states reach 0.95 AUROC for trace correctness on Qwen 1.5B–72B
(0.79 from the first step) — the signal EXISTS at our scale. But four intervention
strategies all fail: the signal is **diagnostic, not causal**. Consequences:
- FMD = a monitor/flag, not a repair mechanism. Product framing: early-warning,
  abort/restart routing, verification triggering — never "auto-fix."
- Trace-level correctness is proven; first-mistake LOCALIZATION (which token/step) is
  the unproven, harder quantity — and it is exactly what Phase 0 measures.

## Phase 0 — Feasibility gate (kill-test, ~$0 on shinobi, ≤2 days)

Data: 500 CoT trajectories from Qwen2.5-1.5B-Instruct on the existing battery pool
(temperature 0.7, n=8/problem on 250 problems → ~2000 traces, keep 500 balanced).

Labels: ground-truth trace correctness from battery answers (free); first-mistake
STEP position labeled by Qwen2.5-7B-Instruct as judge (prompt returns step number),
spot-checked by manual audit of 30 traces (target: ≥80% judge/human agreement, else
re-prompt or switch to program-of-thought re-derivation for labeling).

Probe: logistic regression (L2, C=0.1, StandardScaler) on last-token hidden states,
layers 8–24, per layer. Two targets:
  (a) trace-correctness AUROC  — replication control; expect ~0.9 if pipeline is sane
  (b) first-mistake-localization AUROC — token-level "is this step the first mistake"

## Decision criteria (pre-registered)

- (a) ≥ 0.85 AND (b) ≥ 0.75 → **GO**: build FMD head (trained head, distilled from
  probe → per-step deployment monitor) + integrate as Learning Node self-monitor.
- (a) ≥ 0.85 AND 0.65 ≤ (b) < 0.75 → **PIVOT within bet**: trace-level monitor only
  (weaker product but still deployable: "this run is going wrong" alarms).
- (a) < 0.85 or (b) < 0.65 → **STOP FMD at 1.5B**: switch to belief-shift forking
  (arXiv:2609.11061 PROBE-JS, no trained verifier needed) as the localizer; FMD only
  revisited at 7B scale on RunPod.

Multiple seeds: 3 splits of the probe train/test; report mean±sd AUROC.

## Phase 1 (post-GO) — trained FMD head

1. Distill the linear probe into a small trainable head (2-layer MLP on frozen
   backbone hidden states, then optionally unfreeze last 2 layers of backbone).
2. Train on ~20k labeled steps (Phase-0 pipeline scaled), eval on held-out battery.
3. Deployment demo: agent loop where FMD score triggers (i) verification call,
   (ii) restart-from-branch, (iii) escalation to a stronger model — measure success
   rate and wasted-token reduction vs no-monitor (the 8.8M-vs-1.8M waste stat).
4. Product surface: Learning Node integration (nightly learning + live self-monitor).

## Parallel cheap shot (independent of FMD, 1 hour on shinobi)

**Self-Verified Distillation** (arXiv:2605.26132, verified): sample 8 CoT solutions
per battery problem from the 1.5B, keep solutions passing our existing PoT 2-program
gate, SFT 1 epoch, compare held-out vs Tier-0 static arm. Reuses probe_runner +
train_arm + battery as-is. If positive, it is our first GO on the repo.

## Honesty rules (carried over)

Pre-registered thresholds above; publish Phase-0 results whatever they are; no
"first" claims without checking `docs/prior_art.md`; identity satoshilove.
