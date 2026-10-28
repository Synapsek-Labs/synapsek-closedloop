# diag_teacher2.py — quantify contamination of SFT data
import json, sys
sys.path.insert(0, ".")

rows = [json.loads(l) for l in open("runs/node/shinobi-1/work_teacher.jsonl", encoding="utf-8") if l.strip()]
own = [json.loads(l) for l in open("runs/node/shinobi-1/work.jsonl", encoding="utf-8") if l.strip()]


def clean_rate(rs, name):
    ok = [r for r in rs if r["success"]]
    # clean = success with zero NOT FOUND / INVALID steps and minimal length (<= n_hops + 1 turns)
    clean = [r for r in ok
             if not any("NOT FOUND" in str(t.get("obs", "")) or t["kind"] == "junk"
                        or "INVALID" in str(t.get("obs", "")) for t in r["turns"])
             and len(r["turns"]) <= r["n_hops"] + 1]
    print(f"{name}: successes={len(ok)} clean_minimal={len(clean)} "
          f"({len(clean)/max(1,len(ok)):.0%} of successes clean)")


clean_rate(rows, "TEACHER")
clean_rate(own, "STUDENT-own")

# how many successes used the role-skip shortcut (no role lookup at all)?
def shortcut(rs, name):
    ok = [r for r in rs if r["success"]]
    sc = 0
    for r in ok:
        vals = [t["value"].lower() for t in r["turns"]]
        # gold chain includes a role value; a shortcut path never queries it
        # heuristic: fewer lookups than hops + 1, or any NOT FOUND-free path
        if len(r["turns"]) <= r["n_hops"] - 1 + 1:
            sc += 1
    print(f"{name}: successes with shorter-than-gold path (role-skip shortcut): {sc}/{len(ok)}")


shortcut(rows, "TEACHER")
shortcut(own, "STUDENT-own")
