# Learning Node nightly CLI
import argparse, sys
sys.path.insert(0, ".")
from src.node.nightly import collect, train_delta, gate, sync

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", required=True)
    ap.add_argument("--collect", type=int, default=60)
    ap.add_argument("--gate-n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skip-sync", action="store_true")
    a = ap.parse_args()
    rows, tok, model = collect(a.node, a.collect, a.seed)
    del tok, model
    ad = train_delta(a.node, rows, a.seed)
    del rows
    if ad is not None:
        gate(a.node, ad, a.gate_n, seed=a.seed)
        if not a.skip_sync:
            sync(a.node, seed=a.seed)
    else:
        print("[node] no delta -> nothing to gate/sync")