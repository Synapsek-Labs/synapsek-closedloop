#!/usr/bin/env python3
# CODEX-MINER — mines OpenAI Codex CLI rollout files (JSONL) for real agent-work
# trajectories and banks them T2 (practitioner-evidenced) after the lab-tier
# admission gate. House-law compliant: banks TASK + TOOL-CALL STRUCTURE + MACHINE
# OUTPUTS only. Codex assistant prose/reasoning (frontier GPT output) is NEVER banked.
#
# Usage: python codex_miner.py <sessions_dir> <out_bank.jsonl> [--dry-run]
#        sessions_dir = ~/.codex/sessions (mac/linux) or C:\Users\U\.codex\sessions
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from session_miner import lab_tier_violations, MAX_TASK_CHARS, MAX_RESULT_CHARS

ENV_CTX_RE = re.compile(r"<environment_context>.*?</environment_context>", re.DOTALL)
MIN_TOOL_CALLS = 2
TOOL_TYPES = ("custom_tool_call", "function_call")


def _user_text(payload) -> str:
    parts = []
    for item in payload.get("content", []):
        if isinstance(item, dict) and item.get("type") in ("input_text", "text"):
            parts.append(item.get("text", ""))
    t = "\n".join(parts).strip()
    t = ENV_CTX_RE.sub("", t).strip()  # environment blocks are boilerplate, not task
    return t[:MAX_TASK_CHARS]


def _output_text(payload) -> str:
    out = payload.get("output", "")
    if isinstance(out, list):
        out = "\n".join(x.get("text", "") for x in out if isinstance(x, dict))
    return (out or "")[:MAX_RESULT_CHARS]


def extract_rows(sessions_dir: Path):
    rows = []
    for f in sorted(sessions_dir.rglob("rollout-*.jsonl")):
        task, tool_seq, results = None, [], []
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    p = d.get("payload", {})
                    t = p.get("type", "")
                    if t == "user_message" or (t == "message" and p.get("role") == "user"):
                        if task is None:
                            txt = _user_text(p)
                            if txt and not txt.startswith("/") and len(txt) > 8:
                                task = txt
                        # env-only first user turns are boilerplate; later user turns
                        # carry the real task
                    elif t in TOOL_TYPES:
                        tool_seq.append({"name": p.get("name", "tool"),
                                         "arguments": str(p.get("input", ""))[:MAX_RESULT_CHARS]})
                    elif t in ("custom_tool_call_output", "function_call_output"):
                        r = _output_text(p)
                        if r:
                            results.append(r)
        except OSError:
            continue
        if task and len(tool_seq) >= MIN_TOOL_CALLS and len(results) >= MIN_TOOL_CALLS:
            rows.append({"task": task, "tool_seq": tool_seq, "results": results,
                         "source": "codex-session", "node": f.name and f.stat().st_size and "unknown",
                         "ts": int(f.stat().st_mtime), "task_class": "dev-agent-ops",
                         "verifier": "practitioner-evidenced-T2",
                         "sandbox": "codex-workspace",
                         "session_id": f.stem})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir"); ap.add_argument("out"); ap.add_argument("--node", default="unknown")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = extract_rows(Path(a.dir))
    for r in rows:
        r["node"] = a.node
    out_p = Path(a.out)
    already = set()
    if out_p.exists():
        for line in open(out_p, encoding="utf-8"):
            try:
                already.add(json.loads(line)["session_id"])
            except Exception:
                pass
    rej_path = out_p.with_suffix(".rejects.jsonl")
    if rej_path.exists():
        for line in open(rej_path, encoding="utf-8"):
            try:
                already.add(json.loads(line)["session"])  # previously rejected: skip too
            except Exception:
                pass
    rows = [r for r in rows if r["session_id"] not in already]  # dedup: files never re-bank
    banked, rejected = 0, []
    out = Path(a.out)
    if not a.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
    rej_path = out.with_suffix(".rejects.jsonl")
    for r in rows:
        v = lab_tier_violations(r)
        if v or not all(k in r for k in ("source","node","ts","task_class","verifier")):
            rejected.append({"violations": v, "session": r["session_id"]})
            if not a.dry_run:
                with open(rej_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rejected[-1]) + "\n")
            continue
        if not a.dry_run:
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        banked += 1
    print(f"codex: candidates={len(rows)} banked={banked} rejected={len(rejected)}"
          f"{' (dry-run)' if a.dry_run else ''}")
    from collections import Counter
    c = Counter(x for r in rejected for x in r["violations"])
    print("violation histogram:", dict(c.most_common(10)) if c else "none")


if __name__ == "__main__":
    main()