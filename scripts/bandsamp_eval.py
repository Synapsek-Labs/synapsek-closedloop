# Band-sampling kill-test STEP 4: verdict vs FROZEN gates (d8a0ec7).
# Reads the 6 per-model eval JSONs + probe pool; writes bandsamp_verdict.json.
#   python scripts\bandsamp_eval.py   (main .venv or any python)
import json, statistics
from pathlib import Path

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
ARMS = ["A", "B"]
SEEDS = [1, 2, 3]
# dead-group (computation) office classes for the secondary gate
DEADGROUP = {"sum"}


def main():
    rows = [json.loads(l) for l in
            (NODE / "bandsamp_pool.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    band_n = sum(1 for r in rows if 0.0 < r["rate"] < 1.0)
    per_arm = {}
    for arm in ARMS:
        accs, dg = [], []
        for s in SEEDS:
            of = json.loads((NODE / f"office_eval_v2_bs{arm}{s}.json").read_text())
            sf = json.loads((NODE / f"security_eval_v21_bs{arm}{s}.json").read_text())
            af = json.loads((NODE / f"audit_eval_v1_bs{arm}{s}.json").read_text())
            no, ns, na = of["n"], sf["n"], af["n"]
            comp = (of["office_v2_acc"] * no + sf["security_v21_acc"] * ns
                    + af["audit_v1_acc"] * na) / (no + ns + na)
            accs.append(comp)
            d = of["detail"]
            dg.append(sum(1 for k in DEADGROUP if k in d and d[k].get("pass"))
                      / len(DEADGROUP))
        per_arm[arm] = {"accs": accs, "mean": statistics.mean(accs),
                        "deadgroup": statistics.mean(dg)}
    A, B = per_arm["A"], per_arm["B"]
    diff = B["mean"] - A["mean"]
    verdict = {
        "pool_rows": len(rows), "band_rows": band_n,
        "arm_A_mean": A["mean"], "arm_A_accs": A["accs"],
        "arm_B_mean": B["mean"], "arm_B_accs": B["accs"],
        "diff_B_minus_A": diff,
        "deadgroup_A": A["deadgroup"], "deadgroup_B": B["deadgroup"],
        "main_gate_B_beats_A_by_2pts": diff >= 0.02,
        "kill_B_within_noise_of_A": diff <= 0.005,
        "secondary_deadgroup_B_ge_A": B["deadgroup"] >= A["deadgroup"],
        "verdict": ("ACCEPT" if diff >= 0.02 else
                    ("KILL" if diff <= 0.005 else "INCONCLUSIVE")),
    }
    out = NODE / "bandsamp_verdict.json"
    out.write_text(json.dumps(verdict, indent=2))
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()