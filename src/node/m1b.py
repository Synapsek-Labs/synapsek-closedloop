# M1b: SVAMP domain-transfer gate — train on SVAMP (replay-anchored),
# then a FRESH process gates base vs adapter on the SVAMP held-out battery.
from __future__ import annotations
import json, sys

import torch
from peft import PeftModel

from src.node.pot_node import (
    NODE_DIR, eval_pot, load_model, train_student_pot,
)


def _rows(name):
    return [json.loads(l) for l in
            (NODE_DIR / "shinobi-1" / name).read_text().splitlines()
            if l.strip()]


def train(node_id="shinobi-1", out="delta_svamp"):
    rows = _rows("train_svamp.jsonl")
    print(f"[m1b] training on {len(rows)} SVAMP pairs (replay-anchored)")
    train_student_pot(node_id, rows, out_name=out, replay_ratio=1.0,
                      replay_n=None)
    print("[m1b] TRAIN-DONE")


def gate(node_id="shinobi-1", delta="delta_svamp"):
    tasks = _rows("battery_svamp.jsonl")
    tok, model = load_model()
    tok.padding_side = "left"
    base_acc = eval_pot(model, tok, tasks, label="svamp-base")
    del model
    torch.cuda.empty_cache()
    tok2, model2 = load_model()
    tok2.padding_side = "left"
    wrapped = PeftModel.from_pretrained(model2, str(NODE_DIR / node_id / delta))
    wrapped.eval()
    delta_acc = eval_pot(wrapped, tok2, tasks, label="svamp-delta")
    accept = delta_acc >= base_acc + 0.02
    print(f"[svamp-gate] base {base_acc:.1%} vs delta {delta_acc:.1%} -> "
          f"{'ACCEPT' if accept else 'REJECT'}")
    (NODE_DIR / node_id / "gate_svamp.json").write_text(json.dumps(
        {"base_acc": base_acc, "delta_acc": delta_acc, "accepted": accept,
         "n_eval": len(tasks), "domain": "svamp"}))


if __name__ == "__main__":
    ap = None
    mode = sys.argv[1] if len(sys.argv) > 1 else "train"
    (train if mode == "train" else gate)()
