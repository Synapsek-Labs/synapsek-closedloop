# claude_miner.py — mine Claude Code session jsonl for Synapsek data products.
# HOUSE LAW (unchanged): banks USER prompts + tool_use sequences + tool_result
# (own-machine execution outputs) ONLY. Assistant PROSE/REASONING is NEVER banked
# (frontier output, ToS). Same net-URL + blob gates as codex_miner.
# Usage: python claude_miner.py <claude_dir> <out_bank.jsonl> [--dry-run]
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from session_miner import lab_tier_violations, MAX_TASK_CHARS, MAX_RESULT_CHARS
from user_loop_admission import policy_violations

MIN_TOOL_CALLS = 2
BOILER = ("<command-", "<local-command", "Caveat:", "[Request interrupted")


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content
                        if isinstance(x, dict) and x.get("type") == "text")
    return ""


def extract_rows(claude_dir: Path):
    rows = []
    for f in sorted(claude_dir.rglob("*.jsonl")):
        task, tool_seq, results = None, [], []
        try:
            for line in open(f, encoding="utf-8", errors="replace"):
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                t = d.get("type", "")
                m = d.get("message", {}) or {}
                if t == "user":
                    txt = _text(m.get("content"))
                    if task is None and txt and not txt.startswith(BOILER) and len(txt) > 8:
                        task = txt[:MAX_TASK_CHARS]
                elif t == "assistant":
                    for blk in (m.get("content") or []):
                        if isinstance(blk, dict) and blk.get("type") == "tool_use":
                            tool_seq.append({"name": blk.get("name", "tool"),
                                              "arguments": json.dumps(blk.get("input", ""))[:MAX_RESULT_CHARS]})
                elif t == "user" and isinstance(m.get("content"), list):
                    for blk in m["content"]:
                        if isinstance(blk, dict) and blk.get("type") == "tool_result":
                            results.append(_text(blk.get("content"))[:MAX_RESULT_CHARS])
        except OSError:
            continue
        if task and len(tool_seq) >= MIN_TOOL_CALLS:
            rows.append({"task": task, "tool_seq": tool_seq, "results": results,
                         "source": "claude-session", "node": "paragon",
                         "ts": int(f.stat().st_mtime), "task_class": "dev-agent-ops",
                         "verifier": "practitioner-evidenced-T2",
                         "session_id": f.stem})
    return rows


def gate_rows(rows):
    bank, rej = [], []
    for r in rows:
        joined = " ".join((str(r.get(k, "")) for k in ("task",)))
        joined += " " + " ".join(str(x.get("arguments", "")) for x in r["tool_seq"])
        viol = policy_violations({k: r.get(k) for k in ("task", "tool_seq", "results")})
        if viol:
            r["reject_reasons"] = viol
            rej.append(r)
        else:
            bank.append(r)
    return bank, rej


def main():
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("dir")
    a.add_argument("out")
    a.add_argument("--dry-run", action="store_true")
    args = a.parse_args()
    rows = extract_rows(Path(args.dir))
    bank, rej = gate_rows(rows)
    print(f"claude: candidates={len(rows)} banked={len(bank)} rejected={len(rej)}"
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
                fh.write(json.dumps({k: r[k] for k in ("task", "reject_reasons", "session_id")},
                                    ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()