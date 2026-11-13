# Nyx-2 audit battery v2 — GATE instrument for the 8 breadth classes (audit_collector_v2 space).
# Instances: TAIL slice of the generator (14/class, 112 total) - never banked, model-unseen.
# Bars (pre-registered, commit 41c5bf2, frozen BEFORE training): audit_v2_acc >= 0.70.
import os, sys, json, time, importlib.util, datetime
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ac2", os.path.join(HERE, "audit_collector_v2.py"))
AC2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(AC2)

BASE_URL = os.environ.get("NYX_BASE_URL", "http://127.0.0.1:8003/v1/chat/completions")
TAG = sys.argv[1] if len(sys.argv) > 1 else "audit-v2"
NODE = os.path.join(HERE, "..", "runs", "node", "shinobi-1")
SYS = AC2.SYS
TASKS = AC2.gen_tasks()

by_kind = {k: [] for k in range(1, 9)}
for i in sorted(TASKS):
    p, chk = TASKS[i]
    by_kind[1 + i % 8].append((i, p, chk))
EVAL = {k: v[-14:] for k, v in by_kind.items()}  # tail = unseen

def ask(prompt):
    payload = {"messages": [{"role": "system", "content": SYS},
                            {"role": "user", "content": prompt}],
               "temperature": 0.2, "max_tokens": 700, "stream": False}
    r = requests.post(BASE_URL, json=payload, timeout=600)
    r.raise_for_status()
    # AMENDMENT 2026-11-13: strip <think_> envelope before checkers (v1 parity);
    # k4's positional yes-check ("yes" in al[:40]) was broken by the prefix.
    import re as _re
    _enveloped = _re.compile(r"<\s*think\s*>.*?<\s*/\s*think\s*>",
                              _re.DOTALL | _re.IGNORECASE)
    return _enveloped.sub("", r.json()["choices"][0]["message"]["content"] or "").strip()

res, detail = [], []
for k in range(1, 9):
    ok = 0
    for (i, p, chk) in EVAL[k]:
        a = ask(p)
        v = bool(chk(a))
        ok += v
        detail.append({"kind": k, "id": i, "pass": v,
                       "answer": a[:300]})
        time.sleep(0.5)
    acc = ok / len(EVAL[k])
    res.append(acc)
    print(f"[a2:{TAG}] kind {k}: {ok}/{len(EVAL[k])} = {acc:.2f}", flush=True)

overall = sum(res) / len(res)
verdict = "PASS" if overall >= 0.70 else "FAIL"
out = {"tag": TAG, "ts": datetime.datetime.now().isoformat(),
       "audit_v2_acc": overall, "per_class": {k+1: res[k] for k in range(8)},
       "bar": 0.70, "verdict": verdict, "detail": detail}
path = os.path.join(NODE, f"audit_eval_v2_{TAG}_verdict.json")
json.dump(out, open(path, "w"), indent=1)
print(f"[a2:{TAG}] OVERALL {overall:.3f} bar 0.70 -> {verdict}")
