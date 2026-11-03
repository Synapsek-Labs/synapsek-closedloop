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
