# cursor_miner.py — mine Cursor composer chats from state.vscdb for Synapsek data products.
# HOUSE LAW: banks USER prompts (+tool-bubble counts as tool_seq proxy) ONLY.
# Assistant prose/reasoning NEVER banked (frontier output, ToS).
# Usage: python cursor_miner.py <state.vscdb> <out_bank.jsonl> [--dry-run]
import json, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from user_loop_admission import policy_violations

MAX_TASK_CHARS = 2000
MIN_MSGS = 4
BOILER = ("[Request interrupted", "<command-", "Caveat:")


def main():
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("db")
    a.add_argument("out")
    a.add_argument("--dry-run", action="store_true")
    args = a.parse_args()
    db = sqlite3.connect(args.db)
    rows_raw = db.execute(
        "SELECT key, value, ROWID FROM cursorDiskKV WHERE key LIKE 'composerData:%'"
    ).fetchall()
    candidates, bank, rej = 0, [], []
    for key, val, rid in rows_raw:
        try:
            d = json.loads(val if isinstance(val, str) else bytes(val).decode("utf-8", "replace"))
        except Exception:
            continue
        msgs = d.get("fullConversationHeadersOnly") or []
        if not msgs or len(msgs) < MIN_MSGS:
            continue
        user_texts, tool_count, assistant_count = [], 0, 0
        for m in msgs:
            t = m.get("type")
            if t == 1:  # user bubble
                txt = m.get("text") or m.get("grouping", {}).get("textPreview", "") or ""
                if txt and not txt.startswith(BOILER):
                    user_texts.append(txt[:MAX_TASK_CHARS])
            elif t == 2:
                assistant_count += 1
            else:
                tool_count += 1  # non-text bubble classes: tool/action/render types
        if not user_texts:
            continue
        candidates += 1
        row = {"task": user_texts[0], "n_user_turns": len(user_texts),
               "tool_seq": [{"name": f"cursor-bubble-type-8", "arguments": ""} for _ in range(min(tool_count, 500))],
               "results": [], "source": "cursor-session", "node": "paragon",
               "ts": int(time.time()), "task_class": "dev-agent-ops",
               "verifier": "practitioner-evidenced-T2", "session_id": key.split(":")[-1]}
        viol = policy_violations({k: row.get(k) for k in ("task", "tool_seq", "results")})
        if viol:
            row["reject_reasons"] = viol
            rej.append(row)
        else:
            bank.append(row)
    print(f"cursor: candidates={candidates} banked={len(bank)} rejected={len(rej)}"
          + (" (dry-run)" if args.dry_run else ""))
    hist = {}
    for r in rej:
        for v in r["reject_reasons"]:
            hist[v] = hist.get(v, 0) + 1
    print("violation histogram:", hist if hist else "none")
    if not args.dry_run:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "a", encoding="utf-8") as fh:
            for r in bank:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        rp = out.with_suffix(".rejects.jsonl")
        with open(rp, "a", encoding="utf-8") as fh:
            for r in rej:
                fh.write(json.dumps({"task": r["task"][:200], "reject_reasons": r["reject_reasons"],
                                     "session_id": r["session_id"]}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()