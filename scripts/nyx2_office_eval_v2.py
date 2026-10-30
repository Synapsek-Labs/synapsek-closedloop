# Nyx-2 extended office battery (v2) — 22 archetypes: the 10 v1 office
# battery tasks + one FRESH randomized instance of each of the 12 v2
# real-life office archetypes (training seeds are 1000+i; eval seeds are
# 70000+k -> disjoint). Measures whatever model is served at :8001.
#   .venv\Scripts\python.exe scripts\nyx2_office_eval_v2.py <label>
# Writes office_eval_v2_<label>.json
import json, random, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nyx2_base_eval as ev1
import nyx2_office_collector_v2 as c2

OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "model"
RESULTS_F = OUT / f"office_eval_v2_{LABEL}.json"


def build_tasks():
    """[(name, setup, prompt, verify)] — 10 v1 + 12 v2-fresh."""
    tasks = [(n, s, p, v) for (n, s, p, v) in ev1.OFFICE]
    for k, g in enumerate(c2.GENS):
        rng = random.Random(70000 + k)  # disjoint from training seeds 1000+i
        made = g(rng)
        if made is None:
            tasks.append((f"v2_{k + 10}", None, None, lambda: False))
            continue
        setup, prompt, verify = made
        tasks.append((f"v2_{k + 10}", setup, prompt, verify))
    return tasks


def main():
    tasks = build_tasks()
    results = {}
    for name, setup, prompt, verify in tasks:
        if prompt is None:
            results[name] = {"pass": False, "note": "generator empty (skip count)"}
            continue
        t0 = time.time()
        try:
            n_calls = ev1.agent_task(prompt, setup)
            ok = bool(verify())
        except Exception as e:
            n_calls, ok = -1, False
            print(f"[v2:{name}] ERROR {type(e).__name__}: {e}", flush=True)
        secs = round(time.time() - t0, 1)
        results[name] = {"pass": bool(ok), "tool_calls": n_calls, "secs": secs}
        print(f"[v2:{name}] {'PASS' if ok else 'FAIL'} "
              f"({n_calls} calls, {secs}s)", flush=True)

    real = {k: v for k, v in results.items() if "note" not in v}
    acc = sum(v["pass"] for v in real.values()) / len(real)
    summary = {"model": LABEL, "office_v2_acc": acc, "n": len(real),
               "v1_acc": (sum(v["pass"] for k, v in real.items()
                              if not k.startswith("v2_")) /
                          sum(1 for k in real if not k.startswith("v2_"))),
               "v2_acc": (sum(v["pass"] for k, v in real.items()
                              if k.startswith("v2_")) /
                          sum(1 for k in real if k.startswith("v2_"))),
               "detail": results}
    RESULTS_F.write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("model", "office_v2_acc", "v1_acc", "v2_acc")},
                     indent=2), flush=True)


if __name__ == "__main__":
    main()