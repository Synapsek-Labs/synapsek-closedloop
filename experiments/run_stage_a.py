"""Tier-0 Stage A orchestrator: static arm vs loop arm, equal token budget.

Usage (on shinobi, in the venv):
    python -m experiments.run_stage_a --config configs/tier0_stage_a.yaml --seed 17
    python -m experiments.run_stage_a --config configs/tier0_stage_a.yaml --arm loop --seed 17

Writes runs/stage_a/results_seed{N}.json with the pre-registered metrics.
"""
from __future__ import annotations
import argparse, json, random, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch, yaml
from src.cartography import battery
from src.loop import selector
from src.loop.train_arm import load_policy, train_steps
from src.loop.probe_runner import run_battery, solve_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/tier0_stage_a.yaml")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--battery-size", type=int, default=400,
                    help="held-out battery size for non-smoke runs (size change triggers a fresh frozen battery)")
    ap.add_argument("--arm", choices=["static", "loop", "both"], default="both")
    ap.add_argument("--smoke", action="store_true", help="tiny sizes; verifies pipeline end-to-end")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    rng = random.Random(args.seed)
    out_dir = Path(cfg["report"]["out_dir"]); out_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:  # pipeline verification: seconds, not hours
        cfg["data"]["max_len_tokens"] = 128
        cfg["budget"]["total_tokens_per_arm"] = 60_000
        cfg["loop_arm"]["probe_subset_per_cycle"] = 20
        cfg["eval"]["max_new_tokens"] = 64

    # --- battery: build if absent; for REAL runs, require the full-size battery ---
    manifest_path = Path(cfg["data"]["held_out_battery"]).with_suffix(".manifest.json")
    full_n = 40 if args.smoke else args.battery_size
    need_build = not manifest_path.exists()
    if not need_build:
        m = json.loads(manifest_path.read_text())
        need_build = m["n_held_out"] != full_n   # battery size change = fresh frozen battery
    if need_build:
        print("building battery (first run or size mismatch)...")
        manifest = battery.build(n_held_out=full_n,
                                 n_pool=60 if args.smoke else cfg["data"].get("n_pool", 5000),
                                 seed=0)
        print(json.dumps(manifest, indent=2))
    else:
        assert battery.verify_frozen(cfg["data"]["held_out_battery"]) == \
            json.loads(manifest_path.read_text())["held_out_sha256"], "held-out battery drifted!"

    held = battery.load(cfg["data"]["held_out_battery"])
    pool = battery.load(cfg["data"]["probe_pool"])
    print(f"battery={len(held)} pool={len(pool)}")

    tok, model = load_policy(cfg["model"]["name"], cfg["model"]["load_in_4bit"])
    est_tokens = cfg["data"]["max_len_tokens"]  # upper bound per problem

    results = {"seed": args.seed, "arms": {}}

    def evaluate(arm: str, t0: float, tokens_spent: int, extra: dict):
        scored = run_battery(model, tok, held, max_new=cfg["eval"]["max_new_tokens"])
        acc = solve_rate(scored)
        rec = {"held_out_accuracy": acc, "tokens_trained": tokens_spent,
               "wall_hours": round((time.time() - t0) / 3600, 2), **extra}
        results["arms"][arm] = rec
        (out_dir / f"results_seed{args.seed}.json").write_text(json.dumps(results, indent=2))
        print(f"[{arm}] held-out acc={acc:.4f} tokens={tokens_spent}")
        return acc

    # ---------------- STATIC ARM ----------------
    if args.arm in ("static", "both"):
        t0 = time.time()
        static_ids = selector.select_slice(pool, None,
                                           len(pool),   # one epoch over the pool = the arm's budget
                                           strategy="uniform", rng=rng)
        by_id = {p["id"]: p for p in pool}
        probs = [by_id[i] for i in static_ids]
        stat = train_steps(model, tok, probs, cfg["budget"]["lr"],
                           cfg["budget"]["batch_size"], cfg["budget"]["grad_accum"],
                           cfg["data"]["max_len_tokens"])
        evaluate("static", t0, stat["tokens"], {"mean_loss": stat["mean_loss"]})

    # ---------------- LOOP ARM ----------------
    if args.arm in ("loop", "both"):
        t0 = time.time()
        if args.arm == "both":
            # static arm trained on the loaded weights; loop arm must start fresh
            del model; torch.cuda.empty_cache()
            tok, model = load_policy(cfg["model"]["name"], cfg["model"]["load_in_4bit"])

        budget_left = cfg["budget"]["total_tokens_per_arm"]
        difficulty = None
        tokens_spent = 0
        cycle = 0
        by_id = {p["id"]: p for p in pool}
        n_probe = min(cfg["loop_arm"]["probe_subset_per_cycle"], len(pool))
        for cycle in range(cfg["loop_arm"]["cycles"]):
            if cycle > 0:
                sub = rng.sample(pool, n_probe)
                scored = run_battery(model, tok, sub, max_new=cfg["eval"]["max_new_tokens"])
                difficulty = selector.bucket_by_difficulty(scored, cfg["loop_arm"]["buckets"])
                print(f"cycle {cycle} probe solve-rate={solve_rate(scored):.3f}")
            n_slice = min(budget_left // est_tokens, len(pool) // cfg["loop_arm"]["cycles"])
            slice_ids = selector.select_slice(pool, difficulty, n_slice,
                                              strategy=cfg["loop_arm"]["selection"], rng=rng)
            probs = [by_id[i] for i in slice_ids]
            stat = train_steps(model, tok, probs, cfg["budget"]["lr"],
                               cfg["budget"]["batch_size"], cfg["budget"]["grad_accum"],
                               cfg["data"]["max_len_tokens"])
            tokens_spent += stat["tokens"]; budget_left -= stat["tokens"]
            print(f"cycle {cycle}: tokens={stat['tokens']} left={budget_left}")
            if budget_left < est_tokens:
                break
        evaluate("loop", t0, tokens_spent, {"cycles": cycle + 1})

    verdict = {"seed": args.seed, **results["arms"],
               "delta": results["arms"].get("loop", {}).get("held_out_accuracy", 0)
                        - results["arms"].get("static", {}).get("held_out_accuracy", 0)}
    (out_dir / f"verdict_seed{args.seed}.json").write_text(json.dumps(verdict, indent=2))
    print("VERDICT:", json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
