# Execution-Verified Replay-Anchored Adapter Learning: Safe Nightly Self-Improvement for Small Local Models

**Synapsek Labs** — Andrea Zecchinato (Synapsek Labs, Australia)
*Preprint draft v0.1 — 2026-10-29. All numbers in this paper are real outputs of the runs logged in this repository.*

---

## Abstract

We present a complete, cheaply reproducible stack that lets a small (1.5B–8B) open-weight language model **improve itself nightly on commodity hardware** without degrading, by combining four components: (1) **execution-verified data collection**, in which a teacher model's candidate solutions are admitted only if they execute and reproduce a gold answer; (2) **replay-anchored fine-tuning**, mixing 50% context-free generations from the frozen base to prevent catastrophic forgetting; (3) an **adapter bank** in which the base model is never modified, candidate adapters are admitted only after passing a pre-registered held-out battery on the deploying node, and routing selects among admitted adapters; and (4) **SWAP**, a signed federation protocol allowing nodes to exchange verified capabilities that must survive re-verification on the receiver's own hardware.

Across ten pre-registered gate experiments we establish: (a) that naive few-example fine-tuning of a 1.5B model on verified data *consistently degrades* it (seven rejections, −2% to −50% relative); (b) that replay anchoring converts the failure to parity (first accept: +3.0% absolute on a 100-problem held-out battery, n=100 noise band); (c) that **data volume is the decisive axis** — scaling verified programs from 152 to ~400 moves the same recipe from noise (+3%) to a large, replicable gain (+16% and +19% on two independent GPUs); (d) that merging a strong adapter into a 4-bit-quantized base destroys ~85% of its measured gain (+19% wrapped vs +3% merged), validating wrapped-adapter deployment; and (e) a **failure-band law**: verified small-data SFT pays off only when base accuracy on the target domain lies in a ~40–70% band — above it there is no headroom and updates act as noise.

The full pipeline — collection, training, admission, gating, and federation — runs for under US$1 of rented compute per node-night, and we publish the complete negative-result trail.

## 1. Introduction

Small open-weight models (≤10B) are increasingly deployed as local agent controllers, but they do not improve after deployment: fine-tuning them on narrow data famously causes catastrophic forgetting [1], and safe continual learning for local agents lacks a practical, verifiable recipe. We present a system — built and measured end-to-end on a single RTX 5090 workstation ("shinobi") and commodity GPU pods — that turns a frozen small base into a *self-improving* agent substrate:

- **Nyx**: our model family (0.5B–8B, Apache-2.0 bases) trained with the recipe below.
- **The Learning Node**: nightly collect → verify → train → admit loop with a self-monitor for abstention/escalation.
- **Hebri Swarm / SWAP**: federation of admitted, signed, receiver-verified capabilities.

## 2. Method

### 2.1 Execution-verified collection
A 4-bit-quantized 7B teacher writes one program-of-thought (PoT) per problem (batched greedy decoding, left padding). A candidate is kept only if `run_one` executes it in an isolated subprocess and its printed result matches the gold answer within 1e-4. Execution gating yields a zero-label-noise corpus; observed teacher yields: 69% (GSM8K), 77% (SVAMP), ~54% (MATH-easy).

### 2.2 Replay-anchored training
Student LoRA (1 epoch, lr 5e-5, seed 7) on k teacher programs mixed 1:1 with k *context-free* generations sampled from the frozen base (`<|im_start|>assistant\n` prefix, seed 7). The replay mix anchors the base distribution; without it, every narrow update failed (§4.1). Mechanistically this follows the replay-as-forgetting-antidote literature [1].

### 2.3 The adapter bank
The base model is **never modified**. Each candidate adapter is evaluated on the full held-out battery (n=100, fresh process, +2% pre-registered margin); adapters that pass are stored and wrapped (never merged) at load time; a router selects the best admitted adapter or plain base. Admission at n=40 was found to be unsafe (a +15% probe result failed the full battery); n=100 is the default.

### 2.4 SWAP federation
A bank entry is exported as an ed25519-signed manifest (capability name, base-model identity hash, adapter bundle sha256, measured gain, teacher provenance). The importer verifies the signature (TOFU key pinning), checks base-model identity against its own base config hash, stages the adapter in quarantine, and runs its own full admission battery before first routing. Two-node loop test: the receiver independently reproduced the exporter's claimed +16% gain.

## 3. Experimental setup
- Hardware: RTX 5090 32GB (shinobi, Windows, local), RTX 5080 16GB (RunPod community pods), both 4-bit NF4 via bitsandbytes.
- Models: Qwen2.5-1.5B-Instruct student/base (Apache-2.0); Qwen2.5-7B-Instruct teacher (4-bit).
- Batteries: GSM8K PoT (600-problem pool, 100 held out, seed 0); SVAMP; MATH-easy (numeric-answer subset). All gates pre-registered with a +2% margin; the gate rule was never tuned after any verdict.

## 4. Results

### 4.1 The naive-learning catastrophe (seven pre-registered rejections)
Direct few-example fine-tuning of the 1.5B base on verified data, across four method families (SFT ×2 doses, DPO, teacher-SFT, PoT-teacher SFT), *every time* degraded the held-out battery: 30→15, 30→21.7, 30→23.3, 30→15, and corrected PoT-teacher gates 48.0→46.0. Root cause: narrow-data SFT drives catastrophic forgetting [1]. We STOPped this line (recorded in `docs/learning_node_mvp_result.md`) rather than tuning the gate.

### 4.2 Replay anchoring converts failure to parity
With the 1:1 context-free replay mix, the same pipeline produced the first accept on a RunPod 5080: base 47.0% vs adapter 50.0% (+3.0%, n=100). A same-recipe shinobi replication was neutral (48.0%→47.0%, −1.0%): +3% and −1% are both within the n=100 noise band. Conclusion recorded at the time: effect too small; scale the data.

### 4.3 Data volume is the decisive axis
Scaling verified programs 152 → ~400 (with 1:1 replay):

| Node | Programs | Battery | Base | Adapter | Δ | Verdict |
|---|---|---|---|---|---|---|
| RunPod 5080 | ~400 | GSM8K n=100 (wrapped) | 44.0% | 63.0% | **+19.0%** | ADMITTED |
| Shinobi 5090 | 401 | GSM8K n=100 (wrapped) | 38.0% | 54.0% | **+16.0%** | ADMITTED |

Two independent training runs on different GPUs, same recipe, same qualitative outcome. The 152-program regime had been indistinguishable from noise; at ~400 programs the effect is unambiguous.

### 4.4 Wrapped vs merged: quantization destroys most of an adapter's gain
The same 401-program adapter measured twice on the same pod: **+19% wrapped (PeftModel over the 4-bit base) vs +3% merged (`merge_and_unload` into the 4-bit base)**. bitsandbytes emits a rounding warning during 4-bit merges. Practical consequence: for quantized deployment, adapter routing is not merely safer than merging — it preserves roughly 6× more of the measured improvement.

### 4.5 The failure-band law
On SVAMP (easy arithmetic word problems), base accuracy was 79.0% — near ceiling. The validated recipe *regressed* the model (79.0% → 69.0%, REJECT): with no headroom, small-data SFT is pure noise. Combined with GSM8K/SVAMP teacher-yield observations, we state the **failure-band law**: collect and train only on domains where the deploying base scores ~40–70%; outside the band the loop self-selects the domain out (the baseline eval is the gate).

### 4.6 Federation re-verification
Two-node SWAP loop: exporter claimed 38.0%→54.0%; importer ran its own 100-problem battery on the received adapter and measured 38.0%→54.0% (+16.0%), ADMITTED, base untouched, signature verified, hash-verified bundle.

## 5. Economics
Total measured cost of the entire experimental arc (both GPU nodes, all training, all gates, both federation tests): **under US$2 of rented GPU** (~$1.55 on RunPod; shinobi's 5090 is owned). A node-night is one collection (~5 min GPU) + one training (~12 min) + one admission battery (~20 min) on a single consumer GPU.

## 6. Limitations
- n=100 batteries: ±~5% noise band; all claims above report both arms.
- Single model family (Qwen2.5-1.5B base) and single teacher (7B) so far; cross-family transfer (different base families) is designed for (base-identity checks) but not yet measured.
- Domains measured so far are numeric-answer math; the agent (tool-call) domain is designed but not yet measured.
- Wrapped-adapter serving adds adapter-swap latency not yet benchmarked at scale.

## 7. What we claim — and do not
We claim: a reproducible, safe, nearly-free nightly self-improvement loop for small local models; the failure-band and merge-destruction findings; and a verified-capability federation protocol. We do *not* claim novelty of replay [1], adapter routing, or execution-verified distillation in isolation — our contribution is the **integration with measured safety properties and the complete published negative trail**.

## References
[1] Replay-mix mitigation of catastrophic forgetting in LLM fine-tuning — arXiv:2505.13811.
[2] LIMO:Less is More for Reasoning — data-volume/quality findings for small-model reasoning SFT.
[3] R1 distillation family (DeepSeek-R1-Distill-Qwen-1.5B/32B, MIT) — existence proof for frontier→small capability transfer.
[4] Heretic (p-e-w) — automated refusal-direction removal with KL minimization; huihui-ai abliterated model catalog (Apache-2.0/MIT bases).
[5] colibri (JustVugg/colibri, Apache-2.0) — disk-streaming MoE inference: 744B-class models on ~10GB RAM, CPU-only.
[6] Our prior-art register: `docs/prior_art.md` (§5: LOCAL/CURATOR/Floe/FedWeave/RoboFL/EFFEKT/FedTREK-LM landscape).
