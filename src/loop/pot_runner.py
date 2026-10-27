"""PoT batch executor: runs many generated programs in ONE python process.

Usage: python pot_runner.py <codes.json> <results.json>
codes.json: [{"idx": int, "code": str}]
results.json: [{"idx": int, "ok": bool, "number": float|null}]

Replaces ~1-2s-per-launch subprocess churn (observed ~12 min/cycle on Windows)
with a single launch; each program still gets an isolated namespace + timeout.
"""
from __future__ import annotations
import json, re, sys, threading, io, contextlib

TIMEOUT_S = 10


def run_one(code: str) -> tuple[bool, float | None]:
    result = {"ok": False, "number": None}

    def target():
        try:
            buf = io.StringIO()
            g = {"__name__": "__pot__"}
            with contextlib.redirect_stdout(buf):
                exec(code, g)          # isolated namespace, no imports of runner state
            nums = re.findall(r"-?\d[\d,]*\.?\d*", buf.getvalue().strip())
            if nums:
                result["number"] = round(float(nums[-1].replace(",", "")), 4)
                result["ok"] = True
        except Exception:
            pass

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(TIMEOUT_S)
    return result["ok"], result["number"]


def main():
    codes = json.loads(open(sys.argv[1], encoding="utf-8").read())
    out = []
    for item in codes:
        ok, num = run_one(item["code"])
        out.append({"idx": item["idx"], "ok": ok, "number": num})
    json.dump(out, open(sys.argv[2], "w", encoding="utf-8"))


if __name__ == "__main__":
    main()