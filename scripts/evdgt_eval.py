# EVDGT verdict (pre-reg EVDGT_PREREG.md): D vs U vs static-B (bandsamp B mean 0.756944).
# Reads the 6 per-arm eval JSONs (tags eu1..eu3, ed1..ed3); writes evdgt_verdict.json.
import json
from pathlib import Path

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
ARMS = {"U": "ue", "D": "de"}  # file tag mapping: tag is e<arm><seed>
STATIC_B = 0.7569444444444444

def _read(pattern_variants):
    for p in pattern_variants:
        f = NODE / p
        if f.exists():
            return json.loads(f.read_text())
    raise FileNotFoundError(pattern_variants)


accs = {}
for arm in ARMS:
    accs[arm] = []
    for s in "123":
        a = arm.lower()
        of = _read([f"office_eval_v2_e{arm}{s}.json", f"office_eval_v2_e{a}{s}.json"])
        sf = _read([f"security_eval_v21_e{arm}{s}.json", f"security_eval_v21_e{a}{s}.json"])
        af = _read([f"audit_eval_v1_e{arm}{s}.json", f"audit_eval_v1_e{a}{s}.json"])
        no, ns, na = of["n"], sf["n"], af["n"]
        comp = (of["office_v2_acc"] * no + sf["security_v21_acc"] * ns
                + af["audit_v1_acc"] * na) / (no + ns + na)
        accs[arm].append(comp)

mU = sum(accs["U"]) / 3
mD = sum(accs["D"]) / 3
diff_DU = mD - mU
diff_DB = mD - STATIC_B

verdict = {
    "arm_U_mean": mU, "arm_U_accs": accs["U"],
    "arm_D_mean": mD, "arm_D_accs": accs["D"],
    "static_B_mean": STATIC_B,
    "diff_D_minus_U": diff_DU,
    "diff_D_minus_staticB": diff_DB,
    "gate_D_beats_U_by_2pts": diff_DU >= 0.02,
    "gate_D_beats_staticB_by_1pt": diff_DB >= 0.01,
    "kill_D_within_noise_of_U": diff_DU <= 0.005,
    "verdict": ("GO (EVDGT works)" if diff_DU >= 0.02 and diff_DB >= 0.01
                else "KILL (dynamic within noise of uniform)" if diff_DU <= 0.005
                else "AMBIGUOUS (beats uniform but not static band; keep static recipe)"),
}
out = NODE / "evdgt_verdict.json"
out.write_text(json.dumps(verdict, indent=2))
print(json.dumps(verdict, indent=2))
