# Adapter bank — Learning Node v2 architecture (learning_node_v2_plan.md)
#
# INVARIANT: the node's base model is NEVER modified. Learning = adding
# capability adapters to a runtime bank; a router picks adapter-or-base per
# task. Admission gate = probe accuracy vs base on held-out tasks; a failed
# adapter is simply never routed to — rejection is structurally free.
#
# Registry: runs/node/<node>/bank/registry.json
# Adapters: runs/node/<node>/bank/<name>/ (PeftModel dir, never merged)
from __future__ import annotations
import json, random, time
from pathlib import Path

import src.node.nightly as _nightly


def _bank_dir(node_id):
    d = _nightly.NODE_DIR / node_id / "bank"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reg_path(node_id):
    return _bank_dir(node_id) / "registry.json"


def list_bank(node_id):
    p = _reg_path(node_id)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _save(node_id, entries):
    _reg_path(node_id).write_text(
        json.dumps(entries, indent=1), encoding="utf-8")


def add_to_bank(node_id, delta_dir, name, probe_n=40, seed=11,
                require_positive=True):
    """Evaluate a candidate adapter against base on a probe slice; register
    it ONLY if it doesn't hurt. The adapter is stored as a bank entry —
    the base model is never touched."""
    from src.node.pot_node import _ensure_split, eval_pot
    from peft import PeftModel
    import torch
    from experiments.run_longhorizon_demo import load_model

    delta_dir = Path(delta_dir)
    if not (delta_dir / "adapter_config.json").exists():
        print(f"[bank] no adapter at {delta_dir} — skipping")
        return None

    _, held = _ensure_split()
    rng = random.Random(seed)
    tasks = rng.sample(held, min(probe_n, len(held)))

    tok, base = load_model()
    tok.padding_side = "left"
    base_acc = eval_pot(base, tok, tasks, label="bank-base")
    del base
    torch.cuda.empty_cache()

    tok2, base2 = load_model()
    tok2.padding_side = "left"
    m = PeftModel.from_pretrained(base2, str(delta_dir))
    m.eval()
    ad_acc = eval_pot(m, tok2, tasks, label="bank-adapter")
    del m
    torch.cuda.empty_cache()

    gain = ad_acc - base_acc
    accept = (gain > 0) if require_positive else True
    entry = {"name": name, "delta": str(Path("bank") / name),
             "probe_n": len(tasks), "base_acc": base_acc,
             "adapter_acc": ad_acc, "gain": gain,
             "accepted": accept, "added_at": time.strftime("%Y-%m-%d %H:%M")}
    if accept:
        dest = _bank_dir(node_id) / name
        if dest.exists():
            import shutil
            shutil.rmtree(dest)
        import shutil
        shutil.copytree(delta_dir, dest)
    entries = [e for e in list_bank(node_id) if e["name"] != name]
    entries.append(entry)
    _save(node_id, entries)
    print(f"[bank] {name}: base {base_acc:.1%} vs adapter {ad_acc:.1%} "
          f"-> {'ADMITTED' if accept else 'REJECTED (not routed)'}")
    return entry


def route(node_id, capability=None):
    """Pick the best admitted adapter, or None -> plain base model."""
    admitted = [e for e in list_bank(node_id) if e["accepted"]
                and (capability is None or e.get("capability") == capability)]
    if not admitted:
        return None
    return max(admitted, key=lambda e: e["gain"])


def load_routed(node_id, capability=None):
    """Load base + best admitted adapter (wrapped, NOT merged). Returns
    (tok, model, entry-or-None). Caller must not persist these weights."""
    from peft import PeftModel
    from experiments.run_longhorizon_demo import load_model
    entry = route(node_id, capability)
    tok, model = load_model()
    tok.padding_side = "left"
    if entry is None:
        return tok, model, None
    ad = _nightly.NODE_DIR / node_id / entry["delta"]
    model = PeftModel.from_pretrained(model, str(ad))
    model.eval()
    return tok, model, entry


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, ".")
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--add", help="path to candidate delta dir")
    ap.add_argument("--name", required=True)
    ap.add_argument("--probe-n", type=int, default=40)
    ap.add_argument("--route", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for e in list_bank(a.node):
            print(e)
    elif a.route:
        print(route(a.node))
    elif a.add:
        add_to_bank(a.node, a.add, a.name, probe_n=a.probe_n)