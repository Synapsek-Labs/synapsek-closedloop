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
