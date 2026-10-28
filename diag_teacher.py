# diag_teacher.py — why did teacher-data delta gate at 15% (worse than self-data 21.7%)?
import json, statistics, sys
sys.path.insert(0, ".")

rows = [json.loads(l) for l in open("runs/node/shinobi-1/work_teacher.jsonl", encoding="utf-8") if l.strip()]
own = [json.loads(l) for l in open("runs/node/shinobi-1/work.jsonl", encoding="utf-8") if l.strip()]


def stats(rs, name):
    if not rs:
        print(name, "empty")
        return
    tl = [len(r["turns"]) for r in rs]
    fm = [r["first_mistake"] for r in rs if r["first_mistake"] != -1]
    kinds = {}
    for r in rs:
        for t in r["turns"]:
            kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
    tot = max(1, sum(kinds.values()))
    print(f"{name}: n={len(rs)} turns_mean={statistics.mean(tl):.1f} "
          f"fm_mean={statistics.mean(fm):.1f}" if fm else
          f"{name}: n={len(rs)} turns_mean={statistics.mean(tl):.1f} fm=none",
          f"junk%={kinds.get('junk', 0)/tot:.0%} "
          f"lookup%={kinds.get('lookup', 0)/tot:.0%} "
          f"final%={kinds.get('final', 0)/tot:.0%}")


for name, rs in (("TEACHER-SUCC", [r for r in rows if r["success"]]),
                 ("TEACHER-FAIL", [r for r in rows if not r["success"]]),
                 ("STUDENT-SUCC", [r for r in own if r["success"]]),
                 ("STUDENT-FAIL", [r for r in own if not r["success"]])):
    stats(rs, name)

print("\n--- sample teacher SUCCESS trajectory ---")
ok = [r for r in rows if r["success"]]
if ok:
    r = ok[0]
    for i, t in enumerate(r["turns"]):
        print(f"  t{i}: {t['kind']}({t['value'][:40]}) -> {str(t.get('obs'))[:40]}")

print("\n--- sample student SUCCESS trajectory ---")
ok2 = [r for r in own if r["success"]]
if ok2:
    r = ok2[0]
    for i, t in enumerate(r["turns"]):
        print(f"  t{i}: {t['kind']}({t['value'][:40]}) -> {str(t.get('obs'))[:40]}")

print("\n--- turn-value overlap: does the student's SFT data repeat the SAME entity strings? ---")
# vocabulary overlap between teacher successes and student's own successes
def vocab(rs):
    v = set()
    for r in rs:
        for t in r["turns"]:
            v.add(t["value"].lower())
    return v
vt, vo = vocab([r for r in rows if r["success"]]), vocab([r for r in own if r["success"]])
inter = vt & vo
print(f"teacher-succ values={len(vt)} student-succ values={len(vo)} overlap={len(inter)}")
print("overlap sample:", sorted(inter)[:10])
