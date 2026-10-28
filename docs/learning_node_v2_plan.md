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