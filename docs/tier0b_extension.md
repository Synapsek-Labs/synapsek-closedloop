# Tier-0b — Powered Extension (registered 2026-10-27, BEFORE running)

## Why
Tier-0 seeds 17/41 (400-problem battery) produced deltas −1.5% and +3.5% (mean +1.0%),
within noise. Each run costs ~4 min on the 5090, so the correct response to
underpowering is more power, not a premature verdict.

## Design changes (registered before any run)
- Held-out battery: 400 → **1000** problems (GSM8K test split cap: 1319). SE per arm
  drops from ~±1.9% to ~±0.95%. Battery is rebuilt and frozen BEFORE this round's
  training; manifest hash verified at every run start.
- Pool: 5000 → **7473** (full GSM8K train split). Both arms still one epoch.
- Seeds: **17, 41, 97, 113** (4 seeds). ALL results reported, no cherry-picking.
- Arms/loop config unchanged: selection-driven loop (weak-bucket-heavy), 3 cycles.

## Pre-registered verdicts for Tier-0b
- **GO (selection-loop confirmed)** — loop beats static by ≥2% on held-out, consistent
  sign across ≥3 of 4 seeds, and pooled delta significant at ~2 SE.
- **PIVOT (selection insufficient)** — no consistent advantage. Next levers, in order:
  (1) synthesis-driven loop (LoopTool-style), (2) larger pool/multi-domain, (3)
  pretraining-scale loop. Learning Node program unaffected.
- **STOP** — loop significantly WORSE pooled. Document and abandon selection-loop.

## Honesty rules
Same as tier0_plan.md: frozen battery, equal budgets, all seeds reported regardless
of outcome, negative results published.