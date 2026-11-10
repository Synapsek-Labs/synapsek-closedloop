#!/usr/bin/env python3
# SESSION-MINER — mines a Hebri/Hermes profile's session DB for REAL agent work
# trajectories and banks them (T2: practitioner-evidenced) after the admission scan.
# House-law compliant: banks USER TASK + TOOL-CALL STRUCTURE + MACHINE RESULTS only.
# Assistant PROSE (frontier-API output) is NEVER banked — house law: never train on
# or resell frontier outputs. Tool results are local machine outputs, not model text.
#
# Usage: python session_miner.py <profile_state.db> <out_bank.jsonl> [--dry-run]
import argparse, json, re, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from user_loop_admission import policy_violations, provenance_ok

MAX_TASK_CHARS = 2000
MAX_RESULT_CHARS = 800
MIN_TOOL_CALLS = 4  # quality bar: real multi-step work, not casual one-shot sessions

# LAB-TIER destination policy (documented, does NOT touch the end-user scanner):
# our own sessions legitimately operate on Synapsek infrastructure and research
# destinations. These are OUR machines and OUR accounts — recorded here so the
# lab-tier allowlist is explicit and reviewable, not implicit.
LAB_NET_ALLOW = re.compile(
    r"(?:shinobi|arxiv\.org|\.runpod\.|runpod\.io|githubusercontent\.com|github\.com"
    r"|huggingface\.co|hf\.co|pypi\.org|pythonhosted\.org|npmjs\.org|microsoft\.com"
    r"|openrouter\.ai|synapsek|zenodo\.org|w3\.org|localhost|127\.0\.0\.1|192\.168\.0\."
    r"|tailscale|100\.84\.100\.77"
    # common build/docs destinations recorded in dev-agent sessions (benign, well-known)
    r"|apple\.com|macports\.org|brew\.sh|ninja-build\.org|googlesource\.com|ghcr\.io"
    r"|playwright\.dev|webmproject\.org|rubydoc\.info|pytorch\.org|apache\.org"
    r"|aclanthology\.org|pypa\.io)", re.IGNORECASE)


# true destination extraction: URLs and ssh targets only (the end-user scanner's
# fuzzy regex treats command prose like 'curl -s' as a destination; for lab rows
# we re-scan with a strict extractor — documented deviation, same security goal)
DEST_RE = re.compile(r"(?:https?://|ftp://|ssh\s+|scp\s+|curl\s+|wget\s+)"
                     r"([A-Za-z0-9_.\-]+)", re.IGNORECASE)


def lab_tier_violations(row: dict) -> list[str]:
    """Lab-tier gate: real destination check + every other end-user violation class.
    - Destinations: every actual URL/ssh host in the row must match LAB_NET_ALLOW.
    - Encode-blob rows stay REJECTED (buyer security review would flag them).
    - Credential/blast-radius violations from the end-user scanner still apply."""
    v = []
    text = json.dumps(row)
    for m in DEST_RE.finditer(text):
        host = m.group(1).strip(".-")
        if not host:
            continue
        # only treat dotted domains, IPs, and our known bare hosts as destinations;
        # bare flags/words (-s, -o, "the") after command words are prose, not hosts
        is_host = ("." in host or re.match(r"^\d+\.\d+\.\d+\.\d+$", host)
                   or host.lower() in ("localhost", "shinobi", "shinobi-ts"))
        if not is_host:
            continue
        if not LAB_NET_ALLOW.search(host):
            v.append(f"net:{host}")
    v.extend(x for x in policy_violations(row)
             if not x.startswith("net:") and not x.startswith("path-outside-sandbox"))
    # lab rows legitimately touch our own remote machines; path checks against the
    # mac sandbox are not meaningful for ssh-executed paths, but CREDENTIAL and
    # ENCODE violations remain fatal here.
    return v


def extract_rows(db_path: str):
    d = sqlite3.connect(db_path)
    msgs = d.execute(
        "SELECT session_id, role, content, tool_calls, tool_call_id, timestamp "
        "FROM messages ORDER BY id").fetchall()
    by_session = {}
    for sid, role, content, tcs, tcid, ts in msgs:
        by_session.setdefault(sid, []).append((role, content, tcs, tcid, ts))
    rows = []
    for sid, ms in by_session.items():
        task, tool_seq, results, ts = None, [], [], None
        for role, content, tcs, tcid, ts in ms:
            if role == "user" and task is None:
                c = (content or "").strip()
                # skip command-ish/system-ish first turns
                if c and not c.startswith("/") and "SYSTEM" not in c[:20]:
                    task = c[:MAX_TASK_CHARS]
            if role == "assistant" and tcs:
                try:
                    calls = json.loads(tcs) if isinstance(tcs, str) else tcs
                except Exception:
                    continue
                if not isinstance(calls, list):
                    calls = calls.get("tool_calls", calls) if isinstance(calls, dict) else []
                for tc in calls:
                    fn = (tc or {}).get("function", tc) if isinstance(tc, dict) else {}
                    if isinstance(fn, dict) and fn.get("name"):
                        tool_seq.append({"name": fn.get("name"),
                                         "arguments": fn.get("arguments", "")})
            if role == "tool" and content:
                results.append((content or "")[:MAX_RESULT_CHARS])
        if task and len(tool_seq) >= MIN_TOOL_CALLS and len(results) >= MIN_TOOL_CALLS:
            rows.append({"task": task, "tool_seq": tool_seq,
                         "results": results,
                         "source": "lab-session", "node": "andreazecchinato-mac",
                         "ts": ts or int(time.time()),
                         "task_class": "agent-ops",
                         "verifier": "practitioner-evidenced-T2",
                         "sandbox": "/Users/andreazecchinato",
                         "session_id": sid})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db"); ap.add_argument("out"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = extract_rows(a.db)
    out = Path(a.out)
    already = set()
    if out.exists():
        for line in open(out, encoding="utf-8"):
            try:
                already.add(json.loads(line)["session_id"])
            except Exception:
                pass
    rej_path = out.with_suffix(".rejects.jsonl")
    if out.with_suffix(".rejects.jsonl").exists():
        for line in open(rej_path, encoding="utf-8"):
            try:
                already.add(json.loads(line)["session"])  # previously rejected: skip too
            except Exception:
                pass
    rows = [r for r in rows if r["session_id"] not in already]  # dedup: sessions never re-bank
    banked, rejected = 0, []
    if not a.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        seen = 0
        if out.exists():
            seen = sum(1 for _ in open(out, encoding="utf-8"))
    rej_path = out.with_suffix(".rejects.jsonl")
    for r in rows:
        v = lab_tier_violations(r)
        if v or not provenance_ok(r):
            rejected.append({"violations": v, "provenance_ok": provenance_ok(r),
                             "session": r["session_id"]})
            if not a.dry_run:
                with open(rej_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rejected[-1]) + "\n")
            continue
        if not a.dry_run:
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        banked += 1
    print(f"candidates={len(rows)} banked={banked} rejected={len(rejected)}"
          f"{' (dry-run)' if a.dry_run else ''}")
    from collections import Counter
    c = Counter(v for r in rejected for v in r["violations"])
    print("violation histogram:", dict(c) if c else "none")


if __name__ == "__main__":
    main()