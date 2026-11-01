
## NYX V3 "REALLY STRONG" PROGRAM (locked 2026-11-01, user directive: top benchmark + real business reliability)

### HONEST BASELINE (from gauntlet v1 + gates)
- audit: 92.9% battery / 87.5% real-incident strict (~94% substance incl benign) - but NO model (incl GPT-4/CertiK) can promise finding every problem; $2B+ was hacked in 2023-26 despite top audits.
- office: 68.2% battery - assistant-grade on defined tasks, NOT an autonomous business operator: fails multi-step computation (sum/avg/max/filter), no email/calendar/docs tools yet.
- public MMLU-class benchmarks: 1.7B physics says no. Our winnable axis: DOMAIN benchmark top (Nyx's own batteries published as NyxBench) + small-model class (beat Qwen2.5-1.5B/SmolLM3-class on audit+office+DFIR tasks).

### V3 WORKSTREAMS (each = bank cycle on shinobi, gates pre-registered BEFORE data)
1. AUDIT BREADTH v2 collector: add the under-detected-2023-26 classes from NYX_AUDIT_KNOWLEDGE_BASE.md
   (read-only reentrancy, ERC-4626 inflation deeper, ERC-7702, cross-contract compositional bugs,
   gas griefing, first-depositor variants, proxy patterns x risk) -> 800 rows -> joint retrain.
   TARGET: audit battery v2 (add the new classes) >= 80%, benign >= 80 held, other bars held.
2. OFFICE HARD TASKS v3 collector: sum/avg/max/filter/count multi-step failures -> 800 targeted rows
   (chain: read file -> compute -> write result, execution-verified) -> joint retrain.
   TARGET: office battery >= 85% on current 22 (or battery v3 with hard tasks >= 75%).
3. OFFICE CHAINS v4: 3-6 step workflows with state verification (create dirs, generate CSV, filter,
   aggregate, write report). This is the "business operator" ladder rung 1.
4. FORENSICS v3: multi-log incident reconstruction scenarios from the KB's root-cause library.
5. GAUNTLET v2: full real contracts verbatim (Euler/Wormhole/Radiant full source), office multi-step
   suite, forensics scenarios - the published-evidence tier.
6. MULTI-CHAIN: out of scope for 1.7B (documented limit); revisit post-Genesis with bigger base.

### TRUST ANSWER (user question: "fully sure it will find any problem?")
NO - and we never claim it. What we CAN claim: (a) machine-verified training on the archetype space,
(b) measured benign precision (no crying wolf), (c) recommended deployment = Nyx triage + deterministic
tools (Slither/Echidna/Foundry) = the realistic top-1% auditor workflow. Publish limitation honestly.

### ORDER (5090 time, Genesis has pod): audit-breadth (highest value) -> office-hard -> chains -> forensics -> gauntlet v2.


## NYX FAMILY TIER PLAN (LOCKED 2026-11-01, user directive: "lock it in, go ahead")
Tiers, in build order. Every tier: base-measure FIRST (difficulty law), banks stay
the same machine-verified data, LoRA single-delta, gates pre-registered before data.

- TIER 0  Nyx Nano 1.7B (spark-x2.6 base) — current. Finish v3 program: audit-v2
  (collecting) -> retrain -> gate -> office-hard -> office-chains -> forensics v3.
- TIER 1  Nyx Core ~8B — base chosen by MEASUREMENT: dsr1-8b-normal vs qwen3-8b-normal
  on our office/security/audit batteries (40-70% band preferred; whichever is in-band
  and strongest). QLoRA r16, same banks, joint single-delta. Serves ~6-8GB 4-bit.
- TIER 2  Nyx Cyber 30B — hidra-30b-cybersec: (a) evaluate raw on our batteries,
  (b) if strong -> become THE teacher for all future security/forensics banks
  (replacing qwen3coder-30b for security domains), (c) QLoRA-tune into Nyx format
  only if measurement shows gain. 4-bit serve ~17-20GB on 5090.
- TIER 3  Nyx Pro 27B — qwen3.8-27b (or dsr1-32b): QLoRA attempt on 5090 (tight:
  4-bit + r16 + grad checkpointing + 1024 ctx). Go/no-go by Tier-1/2 results.
  Uncensored twins (27b-abliterated, dsr1-32b-abliterated) = defensive DFIR tier
  (malware triage / incident analysis where normal models refuse benign security work).
- TIER 4  Genesis-family rebasing — whole ladder re-bases onto our own base model
  when Genesis-v1 lands. glm-5.3-normal: teacher-only if ever needed (700GB, never local).

RULES: 5090 = Nyx training/serving; RunPod = Genesis only. Big-model training beyond
5090 capacity = joint decision with user (costs must be approved). Uncensored models
used ONLY for defensive blue-team work, never red-team content (LAB_SECURITY_POLICY).

IMMEDIATE SEQUENCE: audit-v2 bank fills -> joint retrain (3,350 rows) -> gate vs
pre-registered bars -> THEN base-measure hidra-30b + dsr1-8b on batteries (Tier 1/2 data).


## TOKEN DIET IMPLEMENTATION PLAN (LOCKED 2026-11-01)
Pillar 4 product. Target: >=60% serving-token reduction at equal task success, MEASURED on
our own Hebri trace workload (200M tok/days baseline). Gates pre-registered before build.

- TD-0 (1d): token metering per turn/model/task-class in the gateway. Baseline = our own traces.
- TD-1 (2-3d): state-file-not-replay: structured agent state + auto-compact at token budget.
  Harness-level (we own Hebri). Gate: -50%+ prompt tokens on long sessions, zero task loss.
- TD-2 (3-5d): VERIFIED CASCADE ROUTER: Nano 1.7B default; verify outputs with our checker
  discipline; escalate to Pro 30B only on verify-fail or hard task classes. Gate: >=95% of
  tokens on Nano, equal end-to-end task success vs Pro-only.
- TD-3 (1-2d): deterministic tool-result compression filters. Gate: -40% tool tokens.
- TD-4 (1d): vLLM speculative decoding (Nano drafts, Pro verifies). Gate: >=2x Pro throughput.
- TOTAL GATE: cost/sub $28.7 -> <=$12 at equal success. Publish the measured table.

Why defensible: routing is common; VERIFICATION-GUIDED cascades require the verified-battery
discipline only our pipeline has. We are also our own best test bed (Hebri nodes = workload).

Product lineup (LOCKED): 1) Hebri nodes (learn-by-doing infra) 2) NYX family (Nano/Core/Pro)
3) Genesis (research bet) 4) Token Diet (serving-cost invention).


## FINAL PLAN LOCK (2026-11-01, user: "make sure this stays as final plan")
Pillars: 1) Hebri nodes 2) NYX family (Nano 1.7B -> Core 8B -> Pro-Sec 27-30B, defensive
verified layer on top of security-capable open bases; public model work stays blue-team,
offensive capability lives in locally-run downloaded bases for authorized use only)
3) Token Diet (TD-0..TD-4) 4) Genesis. Monetization: local-first free tier -> $15 member
/ $49 agent subscriptions (caps + Token Diet stack, 77-84% margins) -> per-audit fees ->
OpenRouter per-token at scale -> funding via Genesis paper. Research (Colibri 2 / big-model
feeding): kill-test FIRST per pre-flight gate, register in internal vault, never public
until launch. Nyx Sec Node for Hebri: blue-box triage (deterministic tools + local Nyx
models + benign-precision discipline + fix re-verification), blue-team product only.


## TIER PLAN REVISION (2026-11-01 ~21:30 UTC, user directive — SUPERSEDES tier specialization)
The 8B and 27B are NOT office+security+audit specialists. The 1.7B stays the only
specialist bundle. The bigger tiers are GENERALIST AGENT/ENGINEER models:

- TIER 0  Nyx Nano 1.7B (spark base): office + security + audit bundle. DONE (joint-v3).
- TIER 1  Nyx Core 8B: GENERALIST - top agentic skills, tool use, coding for developers.
  "A real engineer, top class." Base candidates: qwen3-8b-normal vs dsr1-8b-normal,
  chosen by MEASUREMENT on coding + function-calling + tool-use evals (NOT our audit battery).
  Data: open agentic/coding SFT mixes (function-calling corpora, code-instruct with
  execution verification, agent trajectories; open-weight sources ONLY - ToS rule).
  Our Hebri-verified tool trajectories count as agent-skill data (they are generic tool use).
- TIER 2  Nyx Pro 27-30B: same recipe, bigger (best generic agent/engineer base by
  measurement: qwen3.8-27b vs dsr1-32b).
- TIER 3  CYBERSECURITY VERTICALS: applied AFTER 8B and 27B are complete - added on top
  of the finished generalists with the same joint-bank method (audit/DFIR banks then).

BUILD ORDER: Core 8B data pipeline (open agentic/coding datasets, curated + verified)
-> base measurements (coding/function-calling evals) -> QLoRA -> coding+agent gates ->
Nyx Core 8B. Then Pro 27-30B. Then security verticals.


## INVENTION QUEUE LOCK (2026-11-02, user-approved)
- PAUSED: soup + janas kill-tests (both cloned on shinobi: tools_soup, tools_janas; register updated).
  They now serve bets, not lead.
- ACTIVE ORDER: (1) DBPT band-curriculum pretraining kill-test -> (2) EVDGT execution-verified
  gating -> (3) TGRIT router warm-start (uses banked 3.4M traces) -> fold winners into Genesis
  corpus recipe -> ATN-PT = Genesis 2.0 claim (trajectories-native from scratch).
- PROTECTED (never paused): Core 8B chain collection (banking), Genesis S0b (pod), Nyx 1.7B serving,
  watch daemon. Kill-tests run on spare 5090 capacity only; never evict serving/collection.
- Full register: ~/synapsek-internal/research/GENESIS2_INVENTION_REGISTER.md (vault 1216f45).
