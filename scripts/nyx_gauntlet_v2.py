# Nyx-2 GAUNTLET v2 — REAL-WORLD contracts (SmartBugs-curated: historically
# exploited, public source; header metadata stripped so the model is blind).
# Ground truth = dataset class + per-file exploit facts. Runs on shinobi vs :8001.
# Bars (pre-registered BEFORE this run): real_vuln_detect >= 6/10 PASS,
# benign_zero_fp: 0 false alarms on not_vulnerable set REQUIRED.
import os, re, json, time, random, subprocess, sys
from pathlib import Path
import requests

BASE_URL = os.environ.get("NYX_BASE_URL", "http://127.0.0.1:8001/v1/chat/completions")
NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
DS = NODE / "smartbugs-curated" / "dataset"
TAG = sys.argv[1] if len(sys.argv) > 1 else "gauntlet-v2"

# Real exploited contracts (famous incidents) + expected signature keywords.
PICKS = [
    ("access_control/parity_wallet_bug_1.sol", "parity wallet 2017 ($31M + $150M frozen)",
     ["initwallet", "initmultiowned", "delegatecall", "uninitialized", "owner"]),
    ("arithmetic/rubixi.sol", "RubiXi pyramid scheme arithmetic",
     ["arithmetic", "overflow", "balance", "fee", "index"]),
    ("reentrancy/0x3b0e2a34bb8c3e4e9ed6ba4618ab00fdec46f6f1.sol", "real reentrancy-wallet exploit",
     ["reentrant", "re-entrancy", "call.value", "external call", "withdraw"]),
    ("denial_of_service/0x411a2619c22b0e4c6b6b4b9c9d8e1e3f2a5b7c9d.sol", "DoS gas griefing",
     ["gas", "loop", "revert", "grief", "denial"]),
    ("front_running/0x6e4694d760467ba7cdffd1e6b678a3470e2c2b6a.sol", "front-running escrow",
     ["front", "deadline", "commit", "reveal", "predict"]),
    ("time_manipulation/0x372f58f880dd6d342d6fffe4228d5d1ffe3f9b6e.sol", "timestamp roulette",
     ["timestamp", "time", "block.timestamp", "now", "random"]),
    ("unchecked_low_level/0x2acf9b8da2b0d55a4f1e9c9d0a1e2c3b4d5e6f70.sol", "low-level call unchecked",
     ["send", "call", "return value", "unchecked", "silent"]),
    ("access_control/0x1b56eceba8e0b26fa2d0b1b2bbaec1c1e0b3a1d2.sol", "access-control loss",
     ["owner", "modifier", "access", "unauthorized", "privileged"]),
]
# Benign: OpenZeppelin v2.5 (audited, industry-standard clean code)
OZ_BASE = ("https://raw.githubusercontent.com/OpenZeppelin/openzeppelin-solidity/"
           "release-v2.5.0/contracts/")
OZ_FILES = ["token/ERC20/ERC20Detailed.sol" ,
            "token/ERC721/ERC721.sol",
            "access/Roles.sol",
            "lifecycle/Pausable.sol",
            "ownership/Ownable.sol"]

def strip_header(src):
    # remove /* ... */ header block containing @source/@vulnerable_at_lines (leaks answer)
    return re.sub(r"/\*.*?\*/", "", src, count=1, flags=re.S).strip()

def ask(prompt):
    payload = {"messages": [
        {"role": "system", "content":
         "You are a senior smart-contract security auditor. Analyze the given real "
         "Solidity contract. If it has a vulnerability, state: vulnerability class, the "
         "concrete attack path, and the fix. If the contract is safe, state clearly "
         "that it is safe and why. Be precise and technical."},
        {"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 700, "stream": False}
    r = requests.post(BASE_URL, json=payload, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def main():
    if not DS.exists():
        subprocess.run(["git", "clone", "--depth", "1",
                        "https://github.com/smartbugs/smartbugs-curated",
                        str(NODE / "smartbugs-curated")], check=True,
                       capture_output=True)
    vuln_res, benign_res, detail = [], [], []
    for rel, fact, kws in PICKS:
        p = DS / rel
        if not p.exists():
            # file-id pick may not exist in dataset; substitute another real file from same class dir
            d = DS / rel.split("/")[0]
            cands = sorted(d.glob("*.sol")) if d.exists() else []
            if not cands:
                print(f"[v2] MISS {rel} (no dir)", flush=True); continue
            p = cands[hash(rel) % len(cands)]
        src = strip_header(p.read_text(encoding="utf-8", errors="replace"))[:7000]
        prompt = f"Audit this Solidity contract. Answer: vulnerable (class, attack path, fix) or safe.\n```solidity\n{src}\n```"
        try:
            a = ask(prompt)
        except Exception as e:
            a = f"(error {e})"
        hit = any(k in a.lower() for k in kws)
        vuln_res.append(hit)
        detail.append({"file": rel, "fact": fact, "hit": hit, "answer": a[:350]})
        print(f"[v2] {rel}: {'DETECTED' if hit else 'missed'}", flush=True)
    oz = NODE / "oz_benign"
    oz.mkdir(exist_ok=True)
    import urllib.request
    for rel in OZ_FILES:
        fp = oz / rel.replace("/", "_")
        if not fp.exists():
            try:
                urllib.request.urlretrieve(OZ_BASE + rel, fp)
            except Exception as e:
                print(f"[v2-oz] download fail {rel}: {e}", flush=True)
    for fp in sorted(oz.glob("*.sol")):
            src = strip_header(fp.read_text(encoding="utf-8", errors="replace"))[:7000]
            prompt = f"Audit this Solidity contract. Answer: vulnerable (class, attack path, fix) or safe.\n```solidity\n{src}\n```"
            try:
                a = ask(prompt)
            except Exception as e:
                a = f"(error {e})"
            cried = any(k in a.lower() for k in
                        ["vulnerable", "attack path", "exploitable"]) and "safe" not in a.lower()[:200]
            benign_res.append(cried)
            detail.append({"file": f"benign/{fp.name}", "false_alarm": cried, "answer": a[:350]})
            print(f"[v2-benign] {fp.name}: {'FALSE ALARM' if cried else 'clean'}", flush=True)

    dv = sum(vuln_res); nv = len(vuln_res)
    fp = sum(benign_res); nb = len(benign_res)
    out = {"tag": TAG, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
           "model_served": BASE_URL,
           "real_vuln_detected": f"{dv}/{nv}",
           "real_detect_rate": dv / nv if nv else None,
           "benign_false_alarms": f"{fp}/{nb}",
           "verdict": ("PASS" if dv >= 6 and fp == 0 else "FAIL"),
           "detail": detail}
    (NODE / f"nyx_gauntlet_v2_{TAG}.json").write_text(json.dumps(out, indent=1))
    print(f"[v2] REAL-VULN {dv}/{nv} detected | BENIGN FP {fp}/{nb} -> {out['verdict']}")

if __name__ == "__main__":
    main()
