# Tier-0 Pilot — Pre-Registered Experiment Plan

> **Status: registered 2026-10-27, before any run.** Success/failure criteria are fixed
> here first so results cannot be reinterpreted after the fact.

## Question

At equal tokens and FLOPs, does closed-loop curriculum selection (probe -> targeted
data -> retrain) outperform a well-constructed static mixture on **held-out** probes?

## Design

| Parameter | Value |
|---|---|
| Model | random-init small LM (0.1B local pilot; 0.5B confirmation) |
| Arms | S: static mixture fixed up-front · L: 3 closed-loop cycles |
| Budget | identical tokens + FLOPs per arm |
| Seeds | 2 per arm (1+1 minimum if wall-clock constrained) |
| Decision metric | **frozen held-out probe battery** (generated before any training, never trained on) |
| Sanity metric | standard benchmarks (arc-easy, hellaswag-10pct) |

## Pre-registered verdicts

- **GO** — Arm L beats Arm S by a meaningful margin on held-out probes, consistent
  across seeds. Proceed to 0.5B confirmation (~$175 RunPod), then 4B (~$3k).
- **PIVOT** — Arm L wins on *seen* probes only (probe-overfitting). Method moves to
  post-training scale (LoopTool-style, already externally validated); Learning Node
  program unaffected.
- **STOP** — no consistent difference at equal budget. Core assumption falsified for
  <$1k; FMD/node infrastructure is retained regardless.

## Honesty rules

- Held-out probes are generated and locked before the first training run.
- Static arm's mixture is constructed *carefully* (a weak strawman control proves nothing).
- All loss curves, configs, and eval dumps are committed; negative results are published.