# State docs moved
All research state, pre-registrations and internal plans now live in the Synapsek internal vault (private repo). This public repo holds released code and published results only.

## CRON PASS 2026-11-03T01:22Z — ep1-boundary safeguard EVALUATED: CONTINUE branch fired
- Val s1500 = 1.90 (vs 1.93 @s1200): still falling, neither flat nor rising
  -> per the registered safeguard, NO early-stop; run continues to ep2
  (projected ~$88, inside the accepted <$100 envelope).
- Spend re-verified via billing API: $42.4 at 01:22Z (cron's $44.4 was an
  estimate; API is ground truth).
- bandsamp chain (shinobi) at 848/1000 rows, healthy — no action.
- Next watch: ep2 val lines; on completion -> gate on pod, stop-not-
  terminate, backup before any mutation.

## STALL FLAG CLEARED (engineer live check, 2026-11-03T03:40Z)
- bandsamp chain is NOT stalled: bandsamp_A_s3 server (PID 26672/26992
  launcher+child) spawned 13:30:45 on :8005, LISTENING, and serving live
  completions (~44 tok/s, tool_calls in flight) per bandsamp_srv_A_s3.txt.
  Eval-log silence = battery runtime (appends on completion only).
- WATCHER RULE REFINEMENT (registered): for the bandsamp chain, the
  aliveness signal is bandsamp_srv_<seed>.txt traffic (or :8005 request
  activity), NOT the eval log mtime or GPU util. GPU is ~1% during
  tool-exec phases by design (CPU-bound on a loaded machine).
- v2 battery partials (context, verdict pending chain completion):
  mkdir PASS, append PASS; sort/count/avg/max FAIL so far (seeds pending).

## ENGINEER DECISION 2026-11-03 ~13:20Z — Track 1 billing verified; EARLY-STOP AT s2100 VAL

Billing-API ground truth (cron estimates were wrong twice over):
- Nov-3 bucket GPU = $16.31 (~3.1h H200) — the pod was STOPPED for
  ~20h during Nov 3 (silent stop, likely maintenance; resume-from-
  checkpoint worked, run continued at step 1950). Cumulative relaunch
  GPU spend: ~$72 across Nov-2/3 buckets — NOT out of control.
- BUT the pace after resume is slow (~2400-3400s/50 steps vs 1025
  nominal). Completing 1084 remaining steps costs $33-100+ more ->
  projected total $105-178 -> BREACHES the $100 hard ceiling.

DECISION (per the registered s2100 fallback): let the run reach the
s2100 VAL line (~150 steps, ~$6-13), bank the checkpoint, then KILL
TRAINING and STOP the pod (not terminate; disk preserved). Val was
improving only ~0.01/line at ep1 tail — remaining ep2 buys ~0.02-0.05
ppl for $33-100+: negative expected value per dollar.
EXCEPTION: if s2100 val improves >0.05 over 1.89, do NOT kill — hold
and ping the engineer (that would signal ep2 is unexpectedly paying).
On stop: gate on pod later only if a fresh decision funds it; adapter
checkpoints live on the retained 100GB disk.

## TRACK 1 EARLY-STOP EXECUTED 2026-11-04 ~05:15Z (engineer)
- s2100 VAL ppl = 1.88 (new low, delta -0.01 vs 1.89) — far under the
  +0.05 jump exception -> registered early-stop criterion SATISFIED.
- Training process KILLED via direct SSH (pkill; verified — only infra
  procs remain). Pod STOPPED (not terminated): 100GB disk retained with
  all checkpoints (s1500/1800/2100 banked; best val 1.88).
- Core-8B run outcome: CONVERGED, not completed — banked artifact is the
  s2100 checkpoint; full training curve 2.17->...->1.88 recorded for the
  paper. Cost capped inside the envelope (~$72-85 GPU cumulative).
- Ops lesson banked: DIRECT ssh (root@IP -p PORT, from pod API) supports
  one-shot exec — the broken-stdin problem applies only to the PROXY
  path (ssh.runpod.io). Use direct SSH for pod operations.
- Remaining options later: gate the s2100 checkpoint on a fresh burst,
  or resume ep2 in a cheaper window if the model is needed complete.
