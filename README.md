<div align="center">

# synapsek-closedloop

**A 1.5B local model that makes itself smarter every night — verified, gated, and shared.**

*Nyx · Synapsek Auto · Hebri Swarm (SWAP)* — Synapsek Labs, Australia 🇦🇺

</div>

---

## What this is

A complete, measured system for **safe nightly self-improvement of small local models**:

1. **Collect** — a teacher model writes program-of-thought solutions; a solution is kept *only if it executes and reproduces the gold answer* (zero label noise).
2. **Train** — the student LoRA is trained 1:1 with **replay-anchored** context-free generations from the frozen base (prevents catastrophic forgetting — see the negative results).
3. **Admit** — the base model is **never modified**. A candidate adapter passes only a pre-registered, held-out, fresh-process battery (+2% margin, n=100). Fails are kept, documented, and cost nothing.
4. **Share** — **SWAP**: ed25519-signed capability manifests with base-identity checks and **receiver-side re-verification**. No trust in transit; a forged or weak capability simply never gets routed.

## Headline result (2 independent GPUs, same recipe)

| Node | Verified programs | Base | Adapter (wrapped) | Gain |
|---|---|---|---|---|
| RTX 5080 pod | ~400 | 44.0% | 63.0% | **+19%** |
| RTX 5090 (shinobi) | 401 | 38.0% | 54.0% | **+16%** |

## Findings (all pre-registered, negatives included)

- ❌ **Naive narrow-data SFT always degrades small models** — 7 gate rejections (−2% to −50% rel.) before the fix.
- ✅ **Replay anchoring fixes the regime** — first accept (+3%), then:
- 📈 **Data volume is the decisive axis** — 152 programs = noise; ~400 = +16–19%.
- ⚡ **Merging into a 4-bit base destroys ~85% of an adapter's gain** (+19% wrapped vs +3% merged) — route adapters, never merge.
- 🎯 **The failure-band law** — train only where base accuracy is 40–70%; above it, updates are noise (measured: 79%→69% REJECT on an easy domain).

The probe-cartography and first-mistake-detection program (probe batteries, FMD, ForkRL) continues as the **measurement layer** of this loop: `probes/`, `src/fmd/`, `src/forkrl/` — the monitor (loc_cum AUROC 0.918/0.82) is its validated product.

## Architecture

```
nightly (per node, GPU-only):
  collect ──execute-verify──▶ work.jsonl (zero-noise corpus)
     │
  replay-train (student LoRA + 50% context-free replay)
     │
  admission gate (fresh process, held-out battery, +2% margin)
     │ pass                          │ fail
  adapter BANK ◀── router ──▶ rejected (kept, documented)
     │
  SWAP export (signed manifest + adapter bundle)
     └────▶ other nodes: verify sig → base check → quarantine → own battery → admit
```

## Repository layout

```
probes/           probe battery definitions + frozen held-out cartography
src/cartography/  probe runner: model x task x difficulty x format grids
src/loop/         closed-loop curriculum: diagnose -> synthesize -> train -> re-probe
src/fmd/          first-mistake detection head (the self-monitor)
src/forkrl/       detection-guided rollout forking
src/node/         Learning Node: collect, verify, train, bank, gate (pot_node, bank, swarm)
configs/          experiment configs (training arms, budgets, seeds)
docs/             plans, go/pivot/stop criteria, verdicts, surveys
experiments/      run scripts (local 5090 + RunPod bursts)
```

## Quick start

```bash
# shinobi (Windows) — detached nightly run
schtasks /create /tn potnode /tr "cmd /c cd /d C:\Users\User\synapsek-closedloop && .venv\Scripts\python.exe -u -m src.node.pot_node --node shinobi-1 --target 400" /sc once /st 00:00 /f

# federation loop test (two logical nodes, one machine)
.venv\Scripts\python.exe -u -m src.node.swarm --node shinobi-1 --export <capability>
.venv\Scripts\python.exe -u -m src.node.swarm --node shinobi-2 --import swarm_registry\shinobi-1\<capability>\manifest.json
```

## Docs index

| Doc | Content |
|---|---|
| `PAPER.md` | The paper: method, all gate results, findings, limitations |
| `docs/learning_node_v2_plan.md` | v2 plan + every gate verdict (7 rejects → accepts) |
| `docs/learning_node_mvp_result.md` | The naive-learning STOP record |
| `docs/swarm_protocol.md` | SWAP v0: manifests, safety rules, loop-test verdict |
| `docs/synapsek_auto_model.md` | Nyx family, Synapsek Auto product, teacher strategy, colibri rung |
| `docs/nyx_improvement_loop.md` | Failure-driven verified curriculum + RLVR plan |
| `docs/nyx_sec_survey.md` | Security/audit line: uncensored model survey + our moat |
| `docs/prior_art.md` | Prior-art register (novelty discipline) |

## Roadmap

- **M1** multi-domain + agent-domain verified corpora (failure-band domains only — SVAMP lesson applied)
- **M2** Nyx-1 v0 release artifact (merged, tested, attributed)
- **M3** 32B→753B-class open-weight teacher bursts
- **Federation v1** on Hebri gateway transports; credit ledger via Synapsek accounts
- **Nyx-Sec / Nyx-Sec-U** — execution-verified security capability (CTF / sandboxed PoC / tool-workflow gates)

## License

Apache-2.0. Model bases: Qwen2.5/3 (Apache-2.0), DeepSeek-R1 distills (MIT). The method is published openly; the running loop (accumulated cartography, verified corpora, bank registry) is the moat.

## Provenance

All commits authored by `satoshilove` (Synapsek Labs). Every gate verdict in the docs is reproducible from the seeds and scripts in this repo. **We publish our failures.**
