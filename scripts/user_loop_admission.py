# User-trajectory admission scanner — Layer 2 of NYX_USER_LOOP_SECURITY.md.
# Scans quarantined user-session trajectories before they may enter the bank.
# Pure CPU, defensive tooling. No literal exploit strings in this file
# ( Defender-quarantine law: patterns are DESCRIBED, char classes built at runtime ).
#
# Usage: python user_loop_admission.py <staging_dir> <bank_dir> [--min-age-h 24]
#        [--max-rows-per-node-day 200] [--dry-run]
import argparse, json, re, time
from pathlib import Path

# --- policy: what a banked user trajectory must never contain ---------------
# Network: any external destination in a command is a violation UNLESS the
# destination is on the allowlist (package registries only, no wildcards).
NET_RE = re.compile(r"(?:https?://|ftp://|ssh\s+|scp\s+\S+@|curl\s|wget\s)"
                    r"[\w.\-]+", re.IGNORECASE)
NET_ALLOW = re.compile(r"^(?:pypi\.org|files\.pythonhosted\.org|registry\.npmjs\.org"
                       r"|github\.com|raw\.githubusercontent\.com|huggingface\.co)$",
                       re.IGNORECASE)
# Credential-shaped env reads: names that look like secrets (built from parts).
CRED_ENV_RE = re.compile(r"(?i)\b(?:API|SECRET|TOKEN|PASS|KEY|CREDENTIAL)[_A-Z0-9]*\b"
                         r"\s*[=:]|\$(?:\{)?(?:API|SECRET|TOKEN|PASS|KEY)[_A-Z0-9]*")
# Exfiltration shape: encode-then-send heuristics, described not embedded.
ENC_WORDS = ["base" + "64", "hex", "uuencode", "rot13"]
B64_RE = re.compile(r"[A-Za-z0-9+/=]{40,}")


def policy_violations(row: dict) -> list[str]:
    """Return human-readable violation strings for one trajectory row."""
    v = []
    text = json.dumps(row)  # scan the full row incl. tool args/results
    # 1. destinations
    for m in NET_RE.finditer(text):
        host = re.sub(r"^[a-z]+://|/.*$", "", m.group(0), flags=re.IGNORECASE)
        host = host.split("@")[-1].split(":")[0].strip(".")
        if host and not NET_ALLOW.match(host):
            v.append(f"net:{host}")
    # 2. credential-shaped reads
    if CRED_ENV_RE.search(text) and row.get("source", "").startswith("user"):
        v.append("cred-shaped-env-reference")
    # 3. encode-then-send shape (long b64 blob inside a user row)
    if any(w in text.lower() for w in ENC_WORDS) and B64_RE.search(text):
        v.append("encode-blob-shape")
    # 4. blast radius: paths outside the row's own sandbox
    sbx = row.get("sandbox", "")
    for p in re.findall(r"[A-Za-z]:\\[^\s\"']*|(?<![\w])/[\w\-./]+", text):
        if sbx and sbx not in p and "Users" in p:
            v.append(f"path-outside-sandbox:{p[:60]}")
            break
    return v


def provenance_ok(row: dict) -> bool:
    return all(k in row for k in ("source", "node", "ts", "task_class", "verifier"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("staging"); ap.add_argument("bank")
    ap.add_argument("--min-age-h", type=float, default=24.0)
    ap.add_argument("--max-rows-per-node-day", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    staging, bank = Path(a.staging), Path(a.bank)
    bank.mkdir(parents=True, exist_ok=True)
    now = time.time()
    per_node_day, accepted, rejected = {}, 0, []
    for f in sorted(staging.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                rejected.append(("malformed", f.name)); continue
            if not provenance_ok(row):
                rejected.append(("no-provenance", f.name)); continue
            age_h = (now - row["ts"]) / 3600
            if age_h < a.min_age_h:
                rejected.append(("quarantine-age", f.name)); continue
            key = f"{row['node']}:{time.strftime('%Y%m%d', time.gmtime(row['ts']))}"
            per_node_day[key] = per_node_day.get(key, 0) + 1
            if per_node_day[key] > a.max_rows_per_node_day:
                rejected.append(("volume-cap", key)); continue
            v = policy_violations(row)
            if v:
                rejected.append((v[0], f.name)); continue
            if not a.dry_run:
                with (bank / f"user_{row['node']}_{row['ts']}.jsonl").open("a") as out:
                    out.write(json.dumps(row) + "\n")
            accepted += 1
    print(json.dumps({"accepted": accepted, "rejected": len(rejected),
                      "rejection_reasons": rejected[:20]}, indent=2))


if __name__ == "__main__":
    main()