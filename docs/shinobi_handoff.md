# Shinobi Handoff — runbook for the Hebri agent on the 5090 PC

**You are the compute node.** This repo contains a pre-registered experiment
(`docs/tier0_plan.md`). Follow this runbook exactly; report results, don't reinterpret
them. No GPU work has been run yet — you are node #0.

## 0. Verify environment

```bash
nvidia-smi                      # expect RTX 5090, ~32GB
python --version                # need >= 3.10
git clone https://github.com/Synapsek-Labs/synapsek-closedloop.git
cd synapsek-closedloop
python -m venv .venv && . .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
```

`requirements.txt` pins torch for CUDA 12.8+ (Blackwell/5090). If the wheel fails,
install torch per https://pytorch.org for cu128.

## 1. Smoke test (~2 minutes, must pass before anything else)

```bash
python -m experiments.run_stage_a --config configs/tier0_stage_a.yaml --seed 17 --smoke
```

Expected: builds the probe battery once (writes `probes/*.jsonl` + manifest), trains a
tiny number of steps on both arms, evaluates, writes `runs/stage_a/results_seed17.json`.
If it crashes: fix environment, NOT experiment logic; report the traceback to the
orchestrating agent (@ai-engineer).

## 2. Real Stage A run (seed 17, both arms)

```bash
python -m experiments.run_stage_a --config configs/tier0_stage_a.yaml --seed 17
```

- Expected wall-clock: 12–24h on the 5090 (two arms × ~6M tokens each at QLoRA speed;
  the config's token budget is sized for one day — report actual throughput after the
  first cycle so the orchestrator can adjust).
- Run inside `tmux`/a background process; checkpoint-free run (LoRA adapter is small —
  on crash, rerun; the orchestrator decides whether to split arms).
- Never edit the held-out battery (`probes/battery_held_out.jsonl`); the hash is
  verified against `probes/battery_held_out.manifest.json` at startup and tampering
  invalidates the experiment.

## 3. Seed 41 (second seed, per plan)

```bash
python -m experiments.run_stage_a --config configs/tier0_stage_a.yaml --seed 41
```

## 4. Report back (message @ai-engineer with)

1. `runs/stage_a/results_seed{17,41}.json` + `verdict_seed{17,41}.json` contents
2. Actual tokens/sec and wall-clock per arm
3. The battery manifest hash (proves frozen battery)
4. Any deviations from this runbook (there should be none except env fixes)

## Rules

- Do NOT change configs, prompts, selection logic, or verdict criteria mid-run.
- Do NOT push results to the repo yourself unless asked; the orchestrator commits
  results with analysis.
- Commit any *code fixes* on a branch `shinobi/fix-*` with a clear message; never
  force-push main.
