# M1c gate: MATH domain — train (failure-band) then fresh-process gate.
# Also measures BASE accuracy on the math battery BEFORE training decides
# whether the domain is in the failure band (registered rule: 40-70%).
import json, sys

import torch
from peft import PeftModel

from src.node.pot_node import NODE_DIR, eval_pot, load_model, train_student_pot


def _rows(name):
    return [json.loads(l) for l in
            (NODE_DIR / "shinobi-1" / name).read_text().splitlines()
            if l.strip()]


def base_gate(node_id="shinobi-1"):
    tasks = _rows("battery_math.jsonl")
    tok, model = load_model()
    tok.padding_side = "left"
    acc = eval_pot(model, tok, tasks, label="math-base-only")
    in_band = 0.40 <= acc <= 0.70
    print(f"[math] base {acc:.1%} -> {'IN failure band' if in_band else 'OUT of band'}")
    (NODE_DIR / node_id / "base_math.json").write_text(json.dumps(
        {"base_acc": acc, "in_band": in_band}))
    return in_band


def train(node_id="shinobi-1", out="delta_math"):
    rows = _rows("train_math.jsonl")
    print(f"[m1c] training on {len(rows)} MATH pairs (replay-anchored)")
    train_student_pot(node_id, rows, out_name=out, replay_ratio=1.0,
                      replay_n=None)
    print("[m1c] TRAIN-DONE")


def gate(node_id="shinobi-1", delta="delta_math"):
    tasks = _rows("battery_math.jsonl")
    tok, model = load_model()
    tok.padding_side = "left"
    base_acc = eval_pot(model, tok, tasks, label="math-base")
    del model
    torch.cuda.empty_cache()
    tok2, model2 = load_model()
    tok2.padding_side = "left"
    wrapped = PeftModel.from_pretrained(model2, str(NODE_DIR / node_id / delta))
    wrapped.eval()
    delta_acc = eval_pot(wrapped, tok2, tasks, label="math-delta")
    accept = delta_acc >= base_acc + 0.02
    print(f"[math-gate] base {base_acc:.1%} vs delta {delta_acc:.1%} -> "
          f"{'ACCEPT' if accept else 'REJECT'}")
    (NODE_DIR / node_id / "gate_math.json").write_text(json.dumps(
        {"base_acc": base_acc, "delta_acc": delta_acc, "accepted": accept,
         "n_eval": len(tasks), "domain": "math"}))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "collect"
    {"base": base_gate, "train": train, "gate": gate}[mode]()
