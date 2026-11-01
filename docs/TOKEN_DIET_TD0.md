# Token Diet — TD-0: Metering spec + baseline (pre-registered BEFORE any cuts)

## Metering schema (gateway logs one record per turn)
turn_id, session_id, model (nano/pro), class (routing label), prompt_tokens,
completion_tokens, tool_result_tokens (fed back), cache_hit (bool), ts.
Sink: jsonl -> daily rollups. We cannot cut what we do not measure.

## Baseline workload (pre-registered, frozen)
- W1: our own Hebri research trace (this lab's real usage: ~200M tok over days)
- W2: fixed agent task suite (10 office chains + 10 audit jobs) - reproducible,
  same tasks before/after every TD stage, scored by existing batteries.
- Success rule for ALL TD gates: W2 end-to-end success rate UNCHANGED (same
  batteries, same bars). Token numbers alone never count as a win.

## Pre-registered TD gates (frozen)
- TD-1 state-not-replay: >=50% prompt-token cut on long sessions, W2 success unchanged
- TD-2 verified cascade: >=95% of tokens routed to nano, W2 success >= pro-only baseline
- TD-3 tool compression: >=40% tool-token cut, W2 success unchanged
- TD-4 speculative decode: >=2x pro throughput, W2 success unchanged
- TOTAL: serving cost/sub $28.7 -> <=$12 (measured, published table)

## What exists already (no build needed)
- Compaction/HANDOFF pattern: proven in live sessions (TD-1 is formalization)
- Checkers/verification discipline for TD-2 cascade: all batteries
- Both endpoints of the router: nyx nano (1.7B) + upcoming pro (27-30B)
- Our workload: Hebri nodes themselves

## Build order + owner
1. TD-0 gateway metering + baseline capture (W2 suite frozen) - 1 day
2. TD-1 auto-compact + state-file resume in harness - 2-3 days
3. TD-2 cascade router with verify-then-escalate - 3-5 days
4. TD-3 tool filters - 1-2 days (parallel with TD-2)
5. TD-4 vLLM speculative decode config - 1 day (after pro serving set up)
