"""PoT batch executor: runs many generated programs in ONE python process,
CONCURRENTLY (ThreadPool) so hang-timeouts don't serialize into hours.

Usage: python pot_runner.py <codes.json> <results.json>
codes.json: [{"idx": int, "code": str}]
results.json: [{"idx": int, "ok": bool, "number": float|null}]
"""
from __future__ import annotations
import json, re, sys, threading, io, contextlib
from concurrent.futures import ThreadPoolExecutor

TIMEOUT_S = 10
WORKERS = 32


def run_one(code: str) -> tuple[bool, float | None]:
    result = {"ok": False, "number": None}

    def target():
        try:
            buf = io.StringIO()
            g = {"__name__": "__pot__"}
            with contextlib.redirect_stdout(buf):
                exec(code, g)          # isolated namespace
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
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(
            lambda item: (item.get("idx", item.get("cand")), run_one(item["code"])), codes))
    json.dump([{"idx": idx, "ok": ok, "number": num} for idx, (ok, num) in results],
              open(sys.argv[2], "w", encoding="utf-8"))


if __name__ == "__main__":
    main()