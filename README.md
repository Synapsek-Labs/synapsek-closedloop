# Synapsek ClosedLoop

**Closed-loop training for small, honest models.** Synapsek Labs' core research program:
models trained by a probe-driven loop instead of a static mixture — and agents that keep
learning after deployment, on hardware users already own.

> *Synapsek builds models that learn — trained by a closed loop that costs 1/1000th as
> much, and keeps learning on your machine after deployment.*

## The thesis

Frontier training pipelines are blind exactly where new capability lives: group-relative
RL has **zero gradient when every rollout fails**, and static pretraining mixtures spend
most of their compute on data the model already knows. We invert this:

1. **Probe cartography** — systematic, frozen probe batteries that map a model's measured
   failure topology (not leaderboard scores).
2. **Closed-loop curriculum** — the model's own failures generate the next slice of
   training data, at pretraining *and* post-training scale.
3. **Failure-first data** — annotated first-mistake trajectories (FMD head) and
   detection-guided rollout forking (ForkRL) convert wasted failed rollouts into
   verifiable learning signal.
4. **Learning Nodes** — small open models (BitNet-class) that improve nightly from
   verified experience on user hardware, with verification-gated federated merging.

## Repository layout

```
probes/          probe battery definitions + frozen held-out cartography
src/cartography/ probe runner: model x task x difficulty x format grids
src/loop/        closed-loop curriculum: diagnose -> synthesize -> train -> re-probe
src/fmd/         first-mistake detection head: training + inference
src/forkrl/      detection-guided rollout forking for the zero-gradient regime
src/node/        Learning Node: capture, verification gate, delta training
configs/         experiment configs (training arms, budgets, seeds)
docs/            experiment plans, go/pivot/stop criteria, results
experiments/     run scripts (local 5090 + RunPod H100)
```

## Current experiment: Tier-0 pilot (pre-registered)

Two arms, equal tokens & FLOPs, random-init small model:
- **Arm S (control):** static mixture, fixed up-front.
- **Arm L (loop):** identical budget, 3 closed-loop cycles (probe -> targeted data -> retrain).

**Decision metric:** frozen held-out probe battery, 2 seeds.
**GO / PIVOT / STOP criteria:** see `docs/tier0_plan.md` (written before any run).

## License

Apache-2.0. The method is published openly; the running loop (accumulated cartography,
probe batteries, verified trajectory corpus) is the moat.