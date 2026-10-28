# The Nyx improvement loop — how we beat benchmarks (2026-10-29)

## The core insight

Every benchmark that matters scores something CHECKABLE (a numeric
answer, code that passes tests, a tool call that executed). That is
the same property our recipe exploits: execution-verified data.
So "beating benchmarks" and "our recipe" are the same machine:

    eval -> understand failures -> generate VERIFIED fixes -> train
    -> gate -> repeat

## The loop (failure-driven verified curriculum)

1. BASELINE: run Nyx on the target benchmark battery (fresh process,
   pre-registered, no tuning).
2. ERROR TAXONOMY: every failure is categorized — wrong reasoning,
   wrong format, missing knowledge, tool misuse, hallucinated API.
   This is "reading the current model": its own failure profile IS
   the map of what it is missing.
3. TARGETED COLLECT: the teacher (7B -> 32B -> 235B-class) generates
   programs/traces for the FAILURE CLUSTERS ONLY, verified by
   execution as always. Hard-example mining, not random data.
4. REPLAY-TRAIN + ADMISSION: same validated recipe and gate. The
   bank makes every iteration safe (a bad cycle is rejected, base
   never touched).
5. Repeat. Each cycle is ~$0 on shinobi; cycles compound.

What top labs do (RLVR / process supervision) is the same idea with
more compute. Our differentiators: verification is objective, the
bank keeps the base safe, and the swarm parallelizes collection.

## Second lever: RL with verifiable rewards (RLVR)

After 2-3 curriculum cycles: GRPO-style RL on the verified corpus
(reward = execution passes). The current frontier recipe, now legal
for us (open-weight teachers only). Shinobi can run small-model RL;
registered as the step AFTER the curriculum loop shows gains.

## Third lever: read the leaders

- Study the published recipes of open leaders (R1, Qwen3, GLM-5.3
  tech reports — GLM-5.3's card openly documents their agentic/cyber
  eval harnesses; we adopt the eval discipline).
- Distill from the models we now MIRROR locally (32B/30B/235B-class
  open weights, license-clean): their outputs on OUR failure clusters
  are exactly the supervision we lack. "Reading current models" =
  querying them as teachers where we fail.
- colibri: when a task needs frontier ability, the streamed 753B
  GLM-5.3 IS the local frontier reference — generate, verify, train.

## Registered benchmarks (M6 gate)

- GSM8K PoT battery (done, base ~48-51%)
- MATH-easy subset (M1 second domain)
- HumanEval/MBPP-style code battery (execution-verified trivially)
- Agent tool-call battery (execution-verified)
- Gate: cycle N admitted iff battery improves >= +2% fresh-process.

## What we will NOT do

- Train on frontier API outputs (ToS).
- Tune the gate after verdicts. No threshold shopping.
- Claim benchmark wins from models that memorized the test set:
  held-out slices stay held out, published nulls stay published.
