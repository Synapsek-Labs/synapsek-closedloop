# M1c base measurement: eval BASE Qwen2.5-1.5B on the collected MATH-easy problems.
# Failure-band law: only resume collection if base scores 40-70% on the domain.
import json, random, sys
sys.path.insert(0, ".")
from pathlib import Path

from src.node.nightly import NODE_DIR
from src.node.pot_node import eval_pot
from experiments.run_longhorizon_demo import load_model

if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "shinobi-1"
    rows = [json.loads(l) for l in (NODE_DIR / node / "work_math.jsonl").open()
            if l.strip()]
    rng = random.Random(7)
    tasks = rng.sample(rows, min(100, len(rows)))
    tok, model = load_model()
    tok.padding_side = "left"
    acc = eval_pot(model, tok, tasks, label="base-math")
    res = {"domain": "math", "base_acc": acc, "n_eval": len(tasks),
           "source": "work_math.jsonl sample"}
    out = NODE_DIR / node / "base_math.json"
    out.write_text(json.dumps(res))
    print(f"[base-math] {res} -> {out}")
