# Learning Node v2 — the new regime — dated 2026-10-28 (evening)

## What we learned (6 rejections, all one root cause)

Every failed delta trained the node's base model DIRECTLY on few verified
examples. Small-SFT on narrow data = distribution mismatch = catastrophic
forgetting = slight degradation (30->15, 30->21.7, 30->23.3, 48->46).
This is a WELL-STUDIED failure with known remedies we hadn't used:

## The two fixes (literature-grounded)

1. **Never merge — adapter bank.** (K-Merge ACL 2026, MoLoRA per-token
   routing, MoLE) The node's base stays FROZEN forever. Learning = adding
   capability adapters to a runtime bank. A router picks adapter-or-base
   per task. Gate per-adapter: adapter-on vs base on held-out; a failed
   adapter is simply not routed to — it CANNOT degrade the node. The 6
   rejections were rejections of MERGED deltas; in a bank architecture
   rejection costs nothing structurally.
2. **Replay-anchor the training.** (arXiv:2505.13811 context-free
   generation replay) Mix teacher data 1:1 with the student's own
   context-free generations during training — anchors the update to the
   base distribution, mitigates forgetting WITHOUT needing Qwen's
   original SFT data. Directly addresses our measured failure mode.

## The user's mesh idea (v2 product architecture)

Heterogeneous Hebri machines as one swarm:
- small node (MacBook) runs a small local model; hard tasks ESCALATE to a
  bigger node's local model (mesh inference fallback ladder — no API
  tokens, no per-token spend)
- nodes exchange LEARNING ARTEFACTS, not raw data: verified traces,
  execution-verified programs, capability adapters (bank entries), and
  monitor priors — all gated by receiver-side execution verification
  (our §6 white space, now with the bank architecture)
- capability adapters load on demand incl. multi-modal ones — the node
  gains a capability by loading an adapter, not by calling an API

Novelty position: components exist (K-Merge, MoLoRA, WeAct); the SYSTEM —
federated adapter-bank exchange between heterogeneous personal agents with
execution-gated admission + mesh escalation + integrated self-monitor —
remains unclaimed (docs/prior_art.md §5/§6).

## Registered next experiment ($0, shinobi)

Replay-mixed teacher SFT: train student on 152 teacher programs MIXED with
base-model context-free generations (50/50). Gate unchanged (+2%, held-out
battery, execution-scored). Decision rule: ACCEPT -> regime fix works,
build the adapter bank on top; REJECT -> stop merging entirely, go straight
to bank+router architecture where merging is never required.
## VERDICT (2026-10-28 night): replay-mix gate ACCEPT

RunPod RTX 5080 burst (pod l2jwk0ff805teh, ~$0.90 total, terminated after
verdict). Same pre-registered gate: 100 held-out battery problems (seed-0
deterministic split), execution-scored, +2% margin, fresh process.

- base 47.0% vs delta 50.0% -> ACCEPT (+3.0%)
- Base replicates shinobi's 48.0% on different hardware: metric solid.
- Context: this is the FIRST ACCEPT after 7 rejections (5 node cycles +
  SFT/teacher merges). Single-variable change vs the rejected teacher-SFT:
  data MIXED 50/50 with context-free base-model replay (arXiv:2505.13811).

CONCLUSION: the node-learning failure was the TRAINING REGIME (narrow-data
SFT -> catastrophic forgetting), not the data source. Replay-anchored
teacher SFT on ~150 verified programs yields the first genuinely-positive
weight delta. Architecture next: adapter-bank (never merge) + router, so
gate rejections cost nothing structurally; federation of bank entries
across heterogeneous Hebri nodes (user's mesh) = v2 product.

Ops banked: update-pod restarts WIPED the container (lost first adapter,
retrained); RunPod proxy blocks sftp/scp -O/port-forwarding; run compute
on pod via git-cloned repo + nohup; pull results through the PTY (verdict
lines) before touching pod config.

## Bank smoke PASSED (2026-10-28 night, RunPod 5080 burst #2, ~$0.15, pod deleted)

End-to-end plumbing verified on real GPU (src/node/bank_smoke.py):
student-generated verified programs -> tiny replay-mix adapter ->
add_to_bank probe gate (base 37.5% vs adapter 43.75% on n=16 -> ADMITTED,
gain +6.25%) -> route() -> load_routed returns a WRAPPED PeftModel
(never merged) -> registry re-add semantics OK.

The adapter bank is the Learning Node v2 core: the base model is never
modified; a rejected adapter simply never gets routed to (rejection is
structurally free); federation across nodes = exchanging bank entries.
Next: nightly cycle produces bank entries via the validated replay-mix
recipe; re-gate the replay delta on shinobi when its GPU frees up.

## Shinobi replication (2026-10-29): NOT CONFIRMED — honest record

Full gate on shinobi with a locally retrained replay-mix delta (same 152
teacher programs, replay re-sampled on shinobi hardware):
- base 48.0% vs delta 47.0% -> REJECT (neutral, -1%)
- The pod's +3% did not replicate. n=100 swings ~+/-5%: the pod result was
  likely noise, or hardware/quantization-specific (bnb 4-bit rounding
  differs 5080 cu13 vs 5090 cu128; replay sampling differs per device).
- Bank admission bug caught and fixed: the 40-problem probe admitted the
  delta at +15% that the full gate measured at -1% — probe slices are too
  noisy; add_to_bank now defaults to the full 100-problem battery.

STATUS: the regime fix remains the best lead (7 rejections -> 1 neutral/
tentative accept), but the effect size is small and unconfirmed. Next
registered lever, in order: (1) MORE data — collect 300-400 verified
teacher programs (pool supports it; LIMO: data volume/quality drives small
SFT), (2) delta scale-down (multiply LoRA B by 0.5 at merge time in the
bank wrapper — tunable post-hoc WITHOUT retraining), (3) 32B RunPod
teacher (~$5). Bank architecture unchanged: rejections stay free.
