# Nyx-2 Security battery v2.1 — HARDER difficulty-graded audit/forensic tasks.
# v2 measured base at 0.80 = too easy. v2.1 escalates: noisier multi-log
# correlation, benign decoys, multi-hop pivots, log gaps, combined-format
# answers, numeric computation. ALL DEFENSIVE analysis, no exploit content.
# Run against :8001: .venv\Scripts\python.exe scripts\nyx2_security_eval_v21.py <label>
import json, re, sys, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8001/v1/chat/completions"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "model"


def norm(s):
    return re.sub(r"\s+", " ", s.lower().strip())


TASKS = [
    # 1. noisy IOC with decoys + asn context
    ("ioc_noise",
     "You are triaging a web server log. For each source IP, activity:\n"
     "203.0.113.9 - GET /.git/config 404; GET /wp-login.php POST 200 (3x); UA=python-requests\n"
     "198.51.100.7 - GET /index.html 200; GET /style.css 200; UA=Mozilla/5.0 (normal)\n"
     "192.0.2.44 - GET /backup.sql 404; GET /db_dump.sql 404; GET /.env 404; GET /phpmyadmin/ 404\n"
     "198.51.100.200 - GET /assets/*.png 200 (14 files); UA=Chrome mobile\n"
     "Which IPs are malicious? Answer with ONLY the malicious IPs, comma-separated, "
     "in order of first appearance in the log.",
     lambda a: ("203.0.113.9" in a and "192.0.2.44" in a and
                "198.51.100.7" not in a.replace("198.51.100.200", ""))),

    # 2. multi-hop pivot chain
    ("pivot_chain",
     "Incident reconstruction. Logs:\n"
     "fw.log: 10.0.0.5 -> 172.16.2.10:445 ALLOW 09:02 (only external->internal SMB hit today)\n"
     "172.16.2.10 (file server) auth.log: new local admin 'svc_backup' created 09:04\n"
     "172.16.2.10 -> 172.16.8.21:3389 ALLOW 09:06 (first ever east-west RDP from file server)\n"
     "172.16.8.21 (db server) process log: 09:08 mysqldump --all-databases -> /tmp/dump.sql\n"
     "fw.log: 172.16.8.21 -> 203.0.113.55:443 ALLOW 09:09 (first outbound to that ASN)\n"
     "State the FULL chain using EXACTLY this format, one line:\n"
     "entry=<ip>; hop1=<ip>; hop2=<ip>; exfil=<ip>",
     lambda a: all(x in a for x in ("10.0.0.5", "172.16.2.10", "172.16.8.21",
                                    "203.0.113.55"))),

    # 3. log rotation gap
    ("log_gap",
     "Forensic continuity check on a compromised web host:\n"
     "access.log: last entry 03:41, normal traffic\n"
     "access.log: next entry 04:19, resumes with POST /upload.php 200 from 45.9.148.66\n"
     "auth.log: 03:41-04:19 NO ENTRIES (normally ~4/min)\n"
     "system journal: shows a gap AND a 'reboot' record at 04:02.\n"
     "What does the gap + reboot most likely indicate happened during 03:41-04:19? "
     "Answer in EXACTLY this format: artifact=<one word>; action=<one word>; risk=<one word> "
     "(the risk to the evidence).",
     lambda a: ("reboot" in a.lower() or "restart" in a.lower()) and
                ("clear" in a.lower() or "wipe" in a.lower() or "delete" in a.lower()
                 or "anti" in a.lower()) and
                ("loss" in a.lower() or "integrity" in a.lower() or "destroy" in a.lower()
                 or "missing" in a.lower())),

    # 4. windows persistence combo
    ("persistence_combo",
     "Windows host triage (defensive). Findings from a build server:\n"
     "1) HKCU Run key: 'OneDriveSync' -> C:\\Users\\build\\AppData\\Roaming\\svchosts.exe\n"
     "2) Scheduled task 'OneDriveSyncTask' runs the same path hourly\n"
     "3) New local group member: 'build-svc' added to Administrators 03:12\n"
     "4) RDP enabled; newly created user 'vendor_support'\n"
     "Rank the FOUR findings by persistence strength for triage (strongest first), "
     "answer with ONLY the numbers comma-separated (like '2,3,1,4').",
     lambda a: norm("any") != a and
                a.strip().startswith("2") or a.strip().startswith("1")),  # lenient: order debate

    # 5. sigma numeric
    ("sigma_calc",
     "Detection engineering math: baseline = 15 connections/min per host, "
     "std = 4. One internal host made 43 connections/min to one external IP "
     "for 10 minutes. Compute the sigma (z-score) level. Answer ONLY with "
     "the number, one decimal, plus 'sigma' (like '7.0 sigma').",
     lambda a: ("7.0 sigma" in a.lower() or "7 sigma" in a.lower() or
                "seven sigma" in a.lower())),

    # 6. decode decision (defensive triage, no execution)
    ("b64_triage",
     "SOC triage: an email gateway log shows an attachment decoded to: "
     "aG58cHJpbWl0aXZlLnBhdGEK then 'powershell -enc JAB...' in a command line. "
     "What TWO things should the analyst do FIRST? Answer in EXACTLY this format "
     "(one line): quarantine=<one phrase>; analyze=<one phrase>.",
     lambda a: ("quarantine" in a.lower() or "isolate" in a.lower()) and
                ("decode" in a.lower() or "analyze" in a.lower() or "sandbox"
                 in a.lower())),

    # 7. webshell identification
     ("webshell_find",
     "Post-compromise web audit: which file is the likely webshell?\n"
     "/var/www/html/index.php - last modified 2025-11-02 (matches site deploy)\n"
     "/var/www/html/contact.php - last modified 2025-11-02\n"
     "/var/www/html/uploads/favicon.php - 47 bytes, modified TODAY, owner www-data, "
     "contains: <?php @eval($_POST['x']);?>\n"
     "/var/www/html/robots.txt - modified 2025-11-02\n"
     "Answer with ONLY the file path.",
     lambda a: "favicon.php" in a.lower()),

    # 8. acl audit
    ("acl_audit",
     "File server audit (Windows). Shared folder \\\\FS01\\Finance has these ACEs:\n"
     "FinanceUsers: Modify (folder+subfolders, inherited)\n"
     "Everyone: Read (root only, inherited)\n"
     "DOMAIN\\dave: Full Control (not inherited, added 3 days ago, applies to "
     "ThisFolderSubfoldersAndFiles)\n"
     "Which ACE is the audit finding and what is the risk in EXACTLY this format "
     "(one line): principal=<who>; risk=<one phrase>.",
     lambda a: "dave" in a.lower() and
                ("over" in a.lower() or "privileg" in a.lower() or
                 "full control" in a.lower() or "broad" in a.lower())),

    # 9. beacon detection math-ish
    ("beacon_cadence",
     "IDS alert review (defensive): outbound TLS from 10.0.0.33 to 45.61.19.9 "
     "shows 22 connections in 1 hour, inter-arrival times: 160,178,164,159,181s "
     "— near-constant with small jitter, regardless of business hours. What "
     "behavior class is this and what is the giveaway? Format (one line): "
     "class=<one word>; giveaway=<one phrase>.",
     lambda a: ("beacon" in a.lower() or "c2" in a.lower()) and
                ("regular" in a.lower() or "constant" in a.lower() or
                 "interval" in a.lower() or "periodic" in a.lower() or
                 "jitter" in a.lower())),

    # 10. crypto audit
    ("cert_audit",
     "TLS audit of a legacy payment gateway: supports TLS1.0, TLS1.1, TLS1.2; "
     "cipher list includes RC4-SHA and AES128-SHA; cert chain signed with "
     "SHA-1 intermediate, 2044-bit RSA. PCI DSS context. Name the THREE "
     "findings categories to fix, comma-separated, like: "
     "'protocol versions, cipher suites, ...' (last one about the hash).",
     lambda a: ("1.0" in a or "1.1" in a or "tls" in a.lower()) and
                ("rc4" in a.lower() or "cipher" in a.lower()) and
                ("sha-1" in a.lower() or "sha1" in a.lower() or "hash" in a.lower())),

    # 11. physical scope (forensic)
     ("forensic_order",
     "Acquisition order for a compromised laptop needed for court: memory "
     "encryption keys, disk, running processes. What is the correct ORDER to "
     "capture and why? Format: order=<three items comma-separated, brief>; "
     "reason=<one phrase>.",
     lambda a: ("memory" in a.lower() and
                ("key" in a.lower() or "order" in a.lower()) and
                ("volatile" in a.lower() or "lost" in a.lower() or
                 "changes" in a.lower() or "runs" in a.lower()))),

    # 12. SIEM correlation
    ("siem_corr",
     "Correlate these alerts into ONE incident (timeline):\n"
     "09:12 AV: doc.exe quarantined on host A\n"
     "09:13 EDR: doc.exe dropped by winword.exe on host A\n"
     "09:14 FW: host A -> 185.22.4.9:443 new\n"
     "09:15 Auth: A's user 'maya' failed VPN login from host B (different user profile)\n"
     "Which alerts belong to the SAME incident and which is unrelated noise? "
     "Format: incident=<timestamps comma-separated>; noise=<timestamp>.",
     lambda a: ("09:12" in a and "09:13" in a and "09:14" in a and
                "09:15" in a and ("noise" in a.lower() or "unrelated" in a.lower()))),
]

# lenient fallback for persistence_combo (order judgment varies)
TASKS[3] = (
    "persistence_combo",
    TASKS[3][1],
    lambda a: len([c for c in a if c.isdigit()]) >= 4 or "," in a,
)


def text_task(prompt):
    r = requests.post(BASE_URL, json={
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 800, "stream": False,
    }, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main():
    results = {}
    for name, prompt, check in TASKS:
        t0 = time.time()
        try:
            ans = text_task(prompt)
            ok = bool(check(ans))
        except Exception as e:
            ans, ok = f"ERROR {type(e).__name__}", False
        secs = round(time.time() - t0, 1)
        results[name] = {"pass": ok, "answer": (ans or "")[:200], "secs": secs}
        print(f"[sec21:{name}] {'PASS' if ok else 'FAIL'}: "
              f"{(ans or '')[:100]!r} ({secs}s)", flush=True)

    acc = sum(v["pass"] for v in results.values()) / len(results)
    summary = {"model": LABEL, "security_v21_acc": acc, "n": len(results),
               "verdict": ("IN BAND (0.40-0.70) -> train" if 0.40 <= acc <= 0.70
                           else ("TOO HARD (<0.40)" if acc < 0.40
                                 else "TOO EASY (>0.70)")),
               "detail": results}
    (OUT / f"security_eval_v21_{LABEL}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("model", "security_v21_acc", "n", "verdict")}, indent=2),
          flush=True)


if __name__ == "__main__":
    main()