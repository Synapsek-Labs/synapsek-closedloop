
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
