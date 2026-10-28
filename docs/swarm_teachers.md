# Swarm teacher policy (2026-10-29) — who can teach a node

## Principle

Verification is OBJECTIVE (program executed vs gold answer). Anyone can
PROPOSE programs; only execution admits them. So teacher quality is free
— what actually matters for the swarm is teacher LICENSE provenance:
what are we legally allowed to train on.

## Tier A — license-clean teachers (default, unrestricted)

Open-WEIGHT models running on user hardware: GLM, DeepSeek, Qwen
(any size) via local GPUs (5090s, pods, user rigs). Outputs are
trainable per the open-weight licenses. Every node with a GPU can be
a Tier A teacher; a node's teacher_id is recorded per-row in the work
file and carried into SWAP manifests.

## Tier B — API teachers (OpenRouter GLM / DeepSeek / Qwen etc.)

- PROPOSING via an API is always fine (it's just inference).
- TRAINING on API outputs is provider-ToS-dependent; several major
  providers prohibit training on outputs. Do not assume it is allowed.
- Rule: Tier B data rows are tagged `"teacher_class": "api"` plus the
  provider id. Receivers can filter: `accept_teachers=["local:*"]`.
- Before enabling any Tier B provider, check its ToS for
  distillation/training-on-outputs explicitly and record the verdict
  in this file. NO provider is enabled by default.

## Effect on the product

- "Synapsek Auto" (Hebri distribution): small base model download +
  monitor + bank + SWAP client on install. The served model IS the
  node's own routed model — no API tokens needed for what local
  capability covers.
- Every user with any local GPU becomes a potential teacher; a 5090
  node contributes ~400 verified programs per night; the swarm
  aggregates and re-verifies. Knowledge equalizes via verified data
  (cross-model) and adapters (same-model), exactly as designed.
