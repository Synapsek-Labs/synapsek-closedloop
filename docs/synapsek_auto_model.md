# Synapsek Auto — our own model family (plan, 2026-10-29)

## The honest physics

- PRETRAINING from scratch: 1.5B Chinchilla-optimal ≈ 30B tokens ≈
  2.7e20 FLOPs ≈ 500+ GPU-hours on a 5090 (3+ weeks nonstop) or
  ~$1k+ of H100. NOT viable for us, and unnecessary (see below).
- What IS viable and is the entire game: **distill + adapt open bases
  with our verified-data recipe.** Qwen2.5/3 bases are Apache-2.0:
  legally we can fine-tune, rebrand, and distribute with attribution.
  Our replay-anchored + execution-verified + bank-admission stack is
  exactly the machinery for turning a generic open base into a
  Synapsek model.

## The family (NAMED 2026-10-29): Nyx — Synapsek's model family

Product = **Synapsek Auto** (the Hebri experience). Model family =
**Nyx** (Greek goddess of night — short, cool, coined-by-us energy).
Star grades encode size (Nyx = night; the tiers are night sky):

| Model | Base | Role |
|---|---|---|
| **Nyx-Micro** (0.5B) | Qwen2.5-0.5B | colibri controller / laptop CPU |
| **Nyx-1** (1.5B) | Qwen2.5-1.5B (Apache-2.0) | default Hebri node — FLAGSHIP |
| **Nyx-3** (3-4B) | Qwen2.5-3B / Qwen3-4B | prosumer GPU |
| **Nyx-8** (8B) | Qwen3-8B | 5090-class nodes |

Versioning: Nyx-1.1 etc. for retrains. Escalation/streamed frontier
rung is product-level ("Frontier boost"), no model name.

"Super compressed": ship 4-bit (works now — our whole stack runs
4-bit) + optional merged bf16 releases. "Super capable": the swarm
recipe + multi-domain verified data + bank, not magic.

## ORDER (user direction 2026-10-29): MODEL FIRST, nodes second

The starting model must be fully capable BEFORE the node network
launches — Hebri agents get a good day-one model, the swarm then
makes it better. Reordered gates:

- **M1 (now): multi-domain verified data** — second domain
  (SVAMP/MATH-easy) AND an AGENT domain: execution-verified
  tool-call trajectories (the verifier is the tool actually
  running). Agent capability = tool-use + instruction following +
  code; all three are execution-verifiable, so the zero-noise
  recipe applies to the AGENT SKILLS specifically, not just math.
- **M2 (the release): Synapsek Auto 1.5B v0** — merged, tested on
  every domain + an agent-task smoke battery (tool-calls execute,
  answers correct). Ship as Hebri's default local model.
- **M3: 32B/235B-class teacher bursts** to deepen the corpus.
- Node network launches only AFTER M2 passes.

## MoE / colibri (CORRECTED after reading JustVugg/colibri, 2026-10-29)

I was wrong that big MoE needs all experts resident: colibri
(Apache-2.0, pure C, 44k stars) runs 744B MoE models with ~10GB RAM
by STREAMING experts from disk on demand — CPU only, no GPU, runs
GLM-5.2/5.3, DeepSeek V4, Qwen3.8, Kimi K3 etc. on ordinary machines.
This changes the Synapsek Auto architecture:

- **The colibri ladder rung is real**: Synapsek Auto = small dense
  core (agent control, instant, always on) -> SAME MACHINE escalates
  to a frontier MoE streamed from local disk via colibri (user
  downloads weights once, ~20-60GB for the useful slice, zero API
  tokens) -> swarm nodes -> burst pods. Frontier capability without
  recurring cost, exactly the user's "colibri-like system" vision.
- **Sparse activation at THREE levels**: adapter bank (node scale),
  expert streaming (machine scale), MoE (model scale). Same principle,
  three sizes.
- **Training angle**: colibri solves RUNNING; our verified-data
  recipe solves IMPROVING. Open question worth registering: can we
  fine-tune/stream individual EXPERTS (a swarm node contributes an
  improved expert for a domain, shipped and streamed like colibri
  experts)? If yes, the swarm's unit of exchange grows from LoRA
  adapters to MoE experts — same SWAP manifest, bigger payload.
  Registered as M5 (research bet, do not block M1/M2).
- Priority stays M1 -> M2: capable small core first; colibri
  integration is an escalation-tier integration task (wrap `coli
  chat`-style engine behind the router's "escalate" branch).

## Registered phases (pre-registered gates, shinobi-first, $0)

- **M1 (multi-domain transfer, also the science replication):** add a
  SECOND execution-verifiable domain (SVAMP/MATH-easy word problems,
  same executor, different distribution). Collect 400, replay-train,
  full-battery admission on shinobi. Gate: adapter > base on the
  second domain battery. PASS = the recipe is general, and the data
  becomes the first multi-domain Synapsek corpus.
- **M2 (Synapsek Auto 1.5B v0):** merge the admitted M1+PoT adapters
  into a RELEASE artifact evaluated on the merged battery + report.
  This is the first model we can call ours (fine-tuned, tested,
  attributed). Gate: >= base on every domain, +2% on at least one.
- **M3 (richer teachers):** open-weight 32B teacher (pod burst, ~$5)
  for higher-yield, more diverse programs; 27B-class teachers on user
  GPUs via the swarm. License-clean only (no API-teacher data).
- **M4 (compression):** 4-bit ship is already proven; optional:
  pruning/distillation pass IF a customer case demands smaller.

## Teacher strategy (2026-10-29, user direction): best open Chinese model as the well

The existence proof: DeepSeek-R1-Distill-Qwen-1.5B was built by
distilling a frontier open model into the SAME Qwen 1.5B base we use —
and it beat much larger models on math benchmarks. Distillation of a
frontier-adjacent open teacher into small bases is exactly how
"small but top" is made.

- Teacher ladder (license-clean, open weights only, never API):
  Qwen2.5-7B (current, shinobi) -> Qwen3-32B / R1-Distill-Qwen-32B
  (pod ~$5 burst) -> biggest open model that fits burst budgets
  (R1-0528 / Qwen3-235B-class via multi-GPU pods when a domain
  warrants it).
- Trust/"obliterate the phone-home" concern: model WEIGHTS are inert
  data — server connections come from app/serving code, not tensors.
  Our stack is fully local (transformers/vLLM on the user's own
  machine); we audit the serving path, ship no telemetry, and every
  SWAP artifact carries provenance so receivers know exactly what
  they adopted. Synapsek Auto = open Chinese excellence, cleaned,
  verified, and improved by the swarm.
- Honest ceiling: distillation makes small models frontier-CALIBER on
  the verified domains we train (math/code/structured tasks); it does
  not make a 1.5B equal a frontier model on open-ended general chat.
  Our pitch is capability-per-watt + trust + self-improvement, not
  raw scale.

## What makes it "first AI" quality

The moat is not weights — it is (1) the verified-data flywheel
(execution gating means zero label noise), (2) the monitor (knows
when it does not know), (3) the bank (cannot be corrupted by its own
learning), (4) the swarm (learns from every other node nightly).
A 1.5B with that system layer beats a raw 1.5B and costs nothing to
run. That is Synapsek's thesis, now demonstrated end to end.
