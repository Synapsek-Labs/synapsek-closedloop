# Band-Sampling Kill-Test — Pre-Registration (frozen BEFORE any run)
Date: 2026-11-03. Base model: nyx-2-joint-v3 (1.7B, serving). Data: our verified banks (office/security/audit, 3,350 rows).

## Hypothesis
Sampling training data from the learnable band (examples the model gets right 30–70% of the time — per arXiv:2504.03380, EACL 2026) beats uniform sampling on held-out verified tasks.

## Arms (LoRA r16 on 1.7B, same steps, same eval)
- A: uniform sampling (control)
- B: band-sampling (30–70% correctness, estimated via cheap pass@k probe with the base model before training)

## Frozen gates (decided before results)
- Main: B beats A on held-out verified eval by ≥2.0 points (accuracy), mean of 3 seeds each
- Secondary: B ≥ A on the dead-group classes (sum/count/avg/max)
- KILL: if B ≤ A within noise (±0.5 pts), the idea is dead at 1.7B scale — publish null
- Seeds: 3 per arm; any arm that fails to train (loss NaN / no convergence) = its loss, no reruns

## Cost/time
- pass@k probe: ~1h on 5090 (k=3, sampled bank)
- 6 × LoRA runs (1.7B, ~30 min each at small step counts): ~3-4h on 5090
- Eval: held-out 200 verified rows × 6 models: ~2h
Total: <8h on the 5090, $0.

## Known scope caveat (from stack-rewrite dig)
Prior art (2504.03380, DAPO, Kimi k1.5, CDAS) covers learnability band in RL post-training; our claim is narrowed to SFT-from-verified-banks at small scale unless the null kills it.
