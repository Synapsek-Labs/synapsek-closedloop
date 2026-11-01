
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
