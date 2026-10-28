# HANDOFF — Synapsek closed-loop / Nyx

**Written:** 2026-10-29, by the default-profile orchestrator, immediately before retiring the
ai-engineer "Bot Chat" session and switching its model to `z-ai/glm-5.3`.

**Read this first in any new session.** It is the authoritative state snapshot. Every claim below
was verified against the live repo, shinobi, or the OpenRouter/macro data on the date above — nothing
here is from memory.

---

## 1. Why this file exists

The ai-engineer Bot Chat session (`20261027_145924_21d329`) had grown to 432 active messages,
179 tool calls, 2,044 API calls and a ~147,000-token prompt per turn on `z-ai/glm-5.3-flash`.
It entered a retry loop (see §7) and stopped producing turns. The session was retired; this
document carries the state forward so nothing is lost.

Full transcript and a byte-exact DB copy — kept **outside** the repo so nothing private is ever
pushed, at `~/synapsek-backups/ai-engineer-20261029/`:

- `transcript_20261027_145924_21d329.md` (287 KB — every active message with content)
- `state.db` (15 MB — consistent online backup, includes the 3,721 compacted messages too)
- `MEMORY.md`, `USER.md`, `config.yaml`, `errors.log` (pre-change copies)

**The todo list is NOT durable.** `todo_list` state lives only in a session's message history
(`AIAgent._hydrate_todo_store` replays the newest todo tool result). A new session starts with an
empty list. That is why §2 is reproduced verbatim here.

---

## 2. The plan — todo list, revision 2 (verbatim, written 2026-10-29 09:53)

All 9 items were `pending`, 0 completed, at the time of retirement.

| id | content | status |
|---|---|---|
| `m1a` | multi-domain collection — second math domain (SVAMP/MATH-easy) + agent domain (execution-verified tool-call trajectories) on shinobi, 400+ each | pending |
| `m1b` | multi-domain train + admission gate on shinobi — PASS = recipe is general | pending |
| `m2` | Synapsek Nyx-1 v0 release — merged adapter, tested on all domains + agent smoke battery, ship as Hebri default local model | pending |
| `m3` | 32B/235B-class open-weight teacher burst on RunPod (~$5) — deepen corpus | pending |
| `m4` | Colibri integration — wire colibri engine behind router escalate branch (Frontier boost rung) | pending |
| `m5` | bet: expert-level SWAP exchange (fine-tuned MoE experts as swarm payloads) — spike, don't block | pending |
| `f1` | Federation v1: gateway transport swap-in (pairing/authz/peer channels), Mac as second physical node, credit ledger via Synapsek accounts | pending |
| `ops` | shinobi multi-task script (collect+train+gate+export in one schtasks batch), adapter registry service for cross-host transfer | pending |
| `pub1` | AT LAUNCH (M2): public claim "first self-improving local AI model launched in Australia (to our knowledge)" + Zenodo DOI + arXiv submission (endorsement needed — solve pre-M2) | pending |

**Naming drift to be aware of.** The committed work used an older numbering: `m1a` = SVAMP collector,
`m1b` = SVAMP transfer gate, `m1c` = MATH-easy domain. Revision 2 of the todo list folded those into
the new `m1a` (multi-domain). Do not re-do SVAMP/MATH as if they were new — see §3.

---

## 3. Verified experimental state — what is settled

Do not re-run these. They are closed and registered as published negatives (which is the point).

### Tier-0 closed loop
- `docs/tier0_plan.md`, `docs/tier0_verdict_final.md`
- Selection loop: **null**. Synthesis loop: **negative** (mode collapse). SVD: **negative**
  (48.9% vs base 51.5%).
- **Base Qwen2.5-1.5B = 51.5% on our GSM8K battery.**
- **Our QLoRA SFT recipe (lr 2e-4) collapses it to ~11%.** Always include a base-model control arm.

### FMD Phase-0
- `docs/fmd_phase0_verdict.md`, `docs/fmd_plan.md`
- Trace AUROC **0.70–0.72** on both sampled and greedy → **STOP at 1.5B; real negative.**
- `loc_cum` per-step cumulative-error detection **0.92 / 0.82** → **validated product signal**
  (the Learning Node self-monitor). See `docs/learning_node_mvp_result.md`,
  `docs/learning_node_v2_plan.md`, `docs/monitor_proto_result.md`.
- 7B judge labeling is the bottleneck.

### M1a/M1b — second domain, both REJECTED
- **SVAMP gate**: `runs/node/shinobi-1/gate_svamp.json` →
  `{"base_acc": 0.79, "delta_acc": 0.69, "accepted": false, "n_eval": 100, "domain": "svamp"}`
- **POT substrate gate**: `runs/node/shinobi-1/gate_pot.json` →
  `{"base_acc": 0.48, "delta_acc": 0.47, "accepted": false, "n_eval": 100, "margin": 0.02}`
- Verdict commit `79b89e8`. **This produced the failure-band law** (see §4): SVAMP's base was 79%,
  far above the 40–70% band, so there was no headroom to win.

### Carried forward from the retired session (not yet run)

- ~~Next registered: PROBE-JS belief-shift on the 123 labeled traces, then the monitor prototype.~~
  Still open — this is the registered follow-on to FMD Phase-0. 7B judge labeling is the bottleneck.
- Learning Node self-monitor is the validated product signal (`loc_cum` 0.92/0.82); the trace-level
  AUROC path was stopped.

### LLM-generated-code pitfalls hit on this project (hard-won, re-read before writing drivers)

- Generated functions often **return but never print** — the pipeline then records a silent empty
  answer. Require straight-line code ending in `print(answer)`.
- Fenced-code extraction from teacher output needs a **closing-fence cut**, or trailing prose
  corrupts the program.
- **Hung generated code cannot be killed as a Python thread.** Static hang-filter on `input(`,
  `while True`, `sleep` before executing.
- Throughput: batched generation at batch 8 / 512 tokens ≈ 13 s/batch. **Batch 32 + 256-token caps
  ≈ 8× faster** synthesis.

### Other registered results
- `docs/svd_result.md`, `docs/longhorizon_demo_result.md`, `docs/strategy_small_compute.md`
- `docs/prior_art.md` — novelty register (ELPO / belief-shift / PivotOPD occupy fork-localization RL)
- `docs/swarm_protocol.md`, `docs/swarm_teachers.md`, `docs/synapsek_auto_model.md`
- `docs/nyx_improvement_loop.md` — the eval→failure-taxonomy→verified-collect→train→gate loop
- `docs/nyx_sec_survey.md`, `docs/shinobi_handoff.md`

---

## 4. The rules we derived (do not relearn these the hard way)

1. **Failure-band law.** Only collect/train on domains where the base model scores **40–70%**.
   Below 40% there is no room to improve; above 70% there is no headroom to win. SVAMP at 79% base
   was guaranteed to fail before it ran.
2. **Always include a base-model control arm.** Our own SFT recipe destroyed a working model
   (51.5% → 11%) and we only saw it because of the control.
3. **Execution-verified data only.** Every sample is a program whose output was checked by running it.
4. **The bank keeps base safe.** A bad training cycle is rejected at admission; the base is never touched.
5. **Never train on frontier-API outputs** (ToS). Open-weight teachers only — 7B → 32B → 235B class.
6. **Measure base on the new domain BEFORE collecting.** That is what `m1c`'s driver does.

---

## 5. Live run state — M1c MATH-easy is STALLED

Verified on shinobi at 2026-10-29 10:26:

```
schtasks /tn m1c  →  Status: Ready          (NOT running)
runs/node/shinobi-1/math_log.txt  last: "[math] 208/1200 problems, 96 verified"
runs/node/shinobi-1/work_math.jsonl  last write 09:24, 42,514 bytes
```

So: **208 of 1,200 problems attempted, 96 of the 400 verified target banked.** The task is idle, not
crashed visibly — it stopped progressing between 09:24 and 09:26 with the GPU at 1%. The collection
is resumable: it reads `work_math.jsonl` and skips `done_ids`, so restarting continues at 96/400.

Shinobi run inventory (`C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\`):
`work.jsonl` (140 KB), `work_pairs.jsonl` (153 KB), `work_math.jsonl` (42 KB),
`train_svamp.jsonl` (104 KB), `battery_svamp.jsonl` (33 KB),
`gate.json`, `gate_svamp.json`, `gate_pot.json`, dirs `bank/ delta/ delta_pot/ delta_svamp/ delta_dpo/`.

**Not yet done:** no decision has been taken on whether to resume M1c or abandon the MATH domain.
Resume it if the base measured inside the 40–70% band; abandon it if the driver's base measurement
said otherwise. That base measurement is the thing to check first, before spending GPU time.

---

## 6. Repo state

- Mac checkout `/Users/andreazecchinato/synapsek-closedloop`, **HEAD = `b0a1d72`**
  ("paper: abstract economics removed (single-consumer-GPU phrasing)").
- `PAPER.md` v0.1 committed, economics stripped, §5 "What we discovered (vs. what we integrated)"
  added. README rewritten.
- **Shinobi's checkout was at `b87ca66` — one commit behind.** Sync shinobi before any further runs
  so the MATH driver and paper match.
- Working tree on Mac was clean.

---

## 7. What went wrong in the previous session (so it is not repeated)

Three independent faults, all now understood:

1. **Automatic post-turn background review looped.** `auxiliary.background_review` was enabled
   (default `true`) and its review fork retried a permanently-refused
   `skill_manage delete 'remote-gpu-node-setup'` **125 times** between 2026-10-27 15:18 and
   2026-10-29 03:17. The guard (`tools/skill_manager_guards.py::_curator_consolidation_delete_guard`)
   refuses any background delete that does not name an `absorbed_into` umbrella — correctly. The
   fork never changed approach.
   **Fix applied:** `auxiliary.background_review.enabled = false` on the ai-engineer profile.
2. **Calls to skills that do not exist in the profile** — `runpod-burst-experiments` (×12),
   `verified-finetuning` (×1). These are not installed in `profiles/ai-engineer/skills/`.
   Check with `skills_list()` before referencing a skill by name.
3. **Mid-stream drops.** 8× `Stream ended with no finish_reason ... treating as a mid-stream drop`
   → the turn is discarded and the user sees "Your request was not processed." Root cause was a
   ~147K-token prompt on a flash-tier model with 179 tool calls of history: the model could not track
   what it had already tried.

**Lesson:** keep the working session short. If a session passes ~150 messages or the prompt passes
~50K tokens, start a fresh session and reload state from this file. Do not let it grow to 400+.

---

## 8. Next actions, in order

1. **Verify shinobi is on `b0a1d72`** (`cd C:\Users\User\synapsek-closedloop && git log --oneline -1`).
2. **Read the M1c base measurement** for the MATH domain before resuming collection — decides
   resume vs. abandon (§5).
3. **If resuming**, restart `schtasks /run /tn m1c` and watch `math_log.txt` for progress inside
   10 minutes; the previous run wedged silently, so treat a flat log as a failure.
4. **`m1b`** (multi-domain train + admission gate) once collection reaches 400 verified.
5. Only then `m2` (Nyx-1 v0), and `pub1` last — publishing waits until the system is proven, and the
   launch claim is the historic one.

Open decision from the previous session: the user asked how to publish officially (arXiv / Zenodo
DOI / endorsement path) and deferred it to launch time. arXiv needs an endorser — solve before M2.

---

## 9. Environment facts (verified)

- **shinobi** = `ssh shinobi`, 192.168.0.28, RTX 5090 32 GB, venv Python 3.13.16, torch 2.11+cu128.
  Remote shell is **cmd.exe**: no `tail`/`head` (use `findstr`), no `timeout`, and
  `dir /s /b` recursions can exceed a 60 s SSH timeout — target specific paths.
- Kill a stuck run: `C:\Users\User\kill_synth.ps1`.
- `uv` venv has no pip — `uv pip install --python .venv\Scripts\python.exe`.
- RunPod MCP server is configured (`mcp.runpod.io`, OAuth) for GPU bursts.
- Delegation model: `deepseek/deepseek-v4-pro` (set in the profile's `delegation` block).

---

## 10. Maintenance changes applied on 2026-10-29

| change | value |
|---|---|
| ai-engineer main model | `z-ai/glm-5.3-flash` → **`z-ai/glm-5.3`** ($0.0699 in / $1.40 out per M, 1,048,576 ctx) |
| `auxiliary.background_review.enabled` | `true` → **`false`** (stops the loop) |
| Bot Chat session | `20261027_145924_21d329` retitled + archived; fresh Bot Chat minted |
| shinobi checkout | synced to Mac HEAD |
| backups | `~/synapsek-backups/ai-engineer-20261029/` (deliberately outside the public repo) |