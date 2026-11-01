# DBPT KILL-TEST — PRE-REGISTRATION (frozen BEFORE any training run, 2026-11-02)

## Mechanism under test (OPEN per 3-agent research sweep, vault 1216f45)
Band-curriculum pretraining: during FROM-SCRATCH next-token pretraining, compute per-token
losses and backpropagate ONLY on tokens inside the 40-70th-percentile band of the batch
loss distribution (the "learnable middle"; drop too-easy + too-hard tokens).
Closest prior art: ESLM (2505.19893, keeps HIGH-loss tokens), Frontier Learning (2609.35426,
RL post-training bands), curriculum papers (ordering only). Medium band at pretraining = unoccupied.

## Design (identical twins, only the loss mask differs)
- Arch: tiny GPT, 8 layers, d=512, 8 heads (~42M params incl. embeddings w/ GPT-2 vocab).
- Data: WikiText-103-raw, ~300M tokens per arm (6 tok/param), GPT-2 BPE tokenizer.
- Batches: 16 seq x 512 tok. AdamW lr 3e-4, bf16 on the 5090. Same seed/data order.
- ARM A (baseline): standard mean cross-entropy over all tokens.
- ARM B (DBPT): per-token CE -> per-batch 40th/70th percentile band -> masked mean CE.
  (Forward sees everything; only the learning signal is gated. FLOPs matched ~equal;
  any DBPT win is a data-efficiency signal, which is the thesis.)
- Val: held-out 2MB, perplexity every 5k steps, final at end.

## PRE-REGISTERED VERDICT RULES (frozen now)
- SUCCESS (GO -> fold into Genesis corpus recipe): DBPT arm final val ppl >=5% LOWER than baseline.
- INCONCLUSIVE: 0-5% difference -> report honestly, do not fold; run the variant (50-75 band) once.
- FAIL (STOP): DBPT worse -> honest null, published with the same care as the Colibri-2 null.
- Runtime guard: both arms must train to the same step count or the comparison is INVALID.
