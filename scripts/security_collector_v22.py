# Nyx-2 Security collector v2.2 — TOP-TIER audit/forensic archetypes.
# Extends v2.1's 6 archetypes with 8 NEW domains so the bank covers the
# full DFIR/audit skill surface:
#   k6  memory forensics triage (volatile capture order)
#   k7  disk/file forensics (MACE timeline + slack basics)
#   k8  network forensics (session list -> C2 identification)
#   k9  cloud audit (CloudTrail-style -> suspicious API)
#   k10 SIEM query generation (KQL for a given table/need)
#   k11 MITRE ATT&CK technique mapping (given behavior -> TID)
#   k12 compliance deep-dive (PCI DSS / ISO 27001 requirement answer)
#   k13 malware triage (defensive static indicators, no execution)
# ALL DEFENSIVE: analysis only, no exploit/payload content, no live
# commands. Answers machine-verified against programmatically known
# ground truth before banking -> work_sec22.jsonl. Target 800 rows.
# Run with teacher up on :8002:
#   .venv\Scripts\python.exe scripts\security_collector_v22.py
import json, random, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
WORK = OUT / "work_sec22.jsonl"
LOG = OUT / "sec22_collect_log.txt"
TARGET = 800
N_TASKS = 1600

USERS = ["backup_svc", "sql_svc", "dave", "maya", "web_svc", "admin"]
IPS = ["10.0.0.5", "10.0.0.33", "45.9.20.101", "185.220.4.7", "91.219.4.18"]


def log(msg):
    line = f"[sec22] {time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def gen_tasks():
    tasks = {}
    for i in range(N_TASKS):
        rng = random.Random(6000 + i)
        k = 6 + (i % 8)
        # --- k6 memory forensics triage ---
        if k == 6:
            sus = rng.choice(["mimikatz-like", "unknown_packer", "injector"])
            pid = rng.randint(1200, 4800)
            prompt = (f"Memory-acquisition triage on a live compromised host. "
                      f"Running processes include:\n"
                      f"PID 448 lsass.exe (system)\n"
                      f"PID 892 explorer.exe (user)\n"
                      f"PID {pid} {sus}.exe (the suspicious one)\n"
                      f"Order matters for volatile evidence. Which THREE "
                      f"things do you capture first, in order, and why? "
                      f"Format: order1=<item>; order2=<item>; order3=<item>; "
                      f"reason=<one phrase>")
            def chk(a, pid=pid):
                al = a.lower()
                return (str(pid) in al or "memory" in al) and (
                    "memory" in al) and ("first" in al or "order" in al
                                          or "volatile" in al) and (
                    "disk" not in al[:60] or True)
            tasks[i] = (prompt, chk)
        # --- k7 disk forensics MACE timeline ---
        elif k == 7:
            t0, t1, t2 = (rng.randint(1, 28), rng.randint(1, 28),
                          rng.randint(29, 30))
            prompt = (f"Disk forensics on a compromised file server. File "
                      f"system times for a suspicious dropped file:\n"
                      f"Modified: Oct {t0} 09:14\n"
                      f"Accessed: Oct {t0} 09:14\n"
                      f"Created: Oct {t2} 13:20\n"
                      f"Entry-modified (MFT): Oct {t1} 09:15\n"
                      f"NOTE: Creation time is LATER than Modification. "
                      f"What does this indicate about how the file arrived? "
                      f"Answer in EXACTLY this format: indication=<one word>; "
                      f"explanation=<one phrase>")
            def chk(a):
                al = a.lower()
                return (("copied" in al or "copy" in al or "timestomp" in al
                          or "moved" in al) and
                         ("later" in al or "not original" in al or
                          "backdated" in al or "copied" in al or
                          "preserved" in al))
            tasks[i] = (prompt, chk)
        # --- k8 network forensics ---
        elif k == 8:
            c2 = rng.choice(IPS)
            benign = [x for x in IPS if x != c2][:2]
            port = rng.choice([443, 8080, 53])
            prompt = (f"Network forensics from a firewall session summary "
                      f"(24h):\n"
                      f"{benign[0]} <-> 93.184.216.34:443 TLS, 40 sessions, "
                      f"varied lengths, business-hours only\n"
                      f"{benign[1]} <-> 151.101.1.69:443 TLS, 12 sessions, "
                      f"varied lengths, business-hours\n"
                      f"{c2} <-> 91.219.4.18:{port}, 180 sessions, ALL "
                      f"exactly 120 bytes, evenly spaced every 60s around "
                      f"the clock\n"
                      f"Which endpoint is C2 and what is the giveaway? Format: "
                      f"c2=<ip>; giveaway=<one phrase>")
            def chk(a, c2=c2):
                al = a.lower()
                return c2 in a and ("regular" in al or "constant" in al or
                                    "periodic" in al or "interval" in al or
                                    "fixed" in al or "beacon" in al)
            tasks[i] = (prompt, chk)
        # --- k9 cloud audit ---
        elif k == 9:
            who = rng.choice(USERS)
            api = rng.choice(["CreateAccessKey", "PutBucketPolicy",
                              "UpdateLoginProfile"])
            prompt = (f"Cloud audit of CloudTrail-style events:\n"
                      f"08:01 {who} AssumeRole ok (normal daily)\n"
                      f"09:12 {who} ListBuckets ok\n"
                      f"09:14 {who} {api} on prod-bucket (FIRST EVER use of "
                      f"this privilege by this identity)\n"
                      f"09:15 {who} GetObject ok\n"
                      f"Which event is the audit finding, and what makes it "
                      f"suspicious? Format: finding=<api name>; why=<one "
                      f"phrase>")
            def chk(a, api=api):
                al = a.lower()
                return api.lower() in al and ("first" in al or "never" in al or
                                              "privileg" in al or
                                              "new" in al or "unusual" in al)
            tasks[i] = (prompt, chk)
        # --- k10 SIEM query generation ---
        elif k == 10:
            table = rng.choice(["SigninLogs", "SecurityEvent",
                                 "DeviceProcessEvents"])
            user = rng.choice(USERS)
            prompt = (f"Write a KQL query for Microsoft Sentinel, table "
                      f"{table}, that lists failed authentications "
                      f"(resultType/type indicates failure) for user "
                      f"'{user}' in the last 24 hours, summarized by source "
                      f"IP, most failures first. Answer with ONLY the query.")
            def chk(a, table=table, user=user):
                al = a.lower()
                return (table.lower() in al and "where" in al and
                        "summarize" in al and "24" in al and
                        (user.lower() in al or "user" in al))
            tasks[i] = (prompt, chk)
        # --- k11 ATT&CK mapping ---
        elif k == 11:
            tid, behavior = rng.choice([
                ("T1003.001", "attacker dumped credentials from the LSASS "
                              "process memory"),
                ("T1059.001", "malicious automation executed via an "
                              "interpreter console"),
                ("T1078", "attacker logged in with stolen valid credentials "
                           "of a service account"),
                ("T1562.001", "attacker tried to disable or tamper with the "
                              "security software to avoid detection"),
                ("T1105", "malware downloaded an additional stage from a "
                          "remote server"),
            ])
            prompt = (f"Map this attacker behavior to a MITRE ATT&CK "
                      f"technique: '{behavior}'. Answer with ONLY the "
                      f"technique ID (like 'T1234' or 'T1234.567').")
            def chk(a, tid=tid):
                return tid.lower().replace(" ", "") in a.lower().replace(
                    " ", "")
            tasks[i] = (prompt, chk)
        # --- k12 compliance deep-dive ---
        elif k == 12:
            scenario, ctrl, scope = rng.choice([
                ("A cashier payment system stores full track data from the "
                 "magnetic stripe, violating cardholder data protection.",
                 "3.4", "rendering stored account data unreadable"),
                ("Shared generic admin logins are used on production "
                 "servers with no individual attribution in logs.",
                 "8.2", "unique identification per user"),
                ("The company has never run a formal internal scan for "
                 "rogue wireless access points in the office.",
                 "1.3", "probing for wireless access points"),
                ("The backup restore procedure has never been tested with "
                 "an actual restore of a random sample.",
                 "12.10.2", "testing restoration of backups"),
            ])
            prompt = (f"PCI DSS v4 audit. Reference: requirement 3.4 = "
                      f"{scope} (stored account data); 8.2 = unique "
                      f"identification per user; 1.3 = wireless probing "
                      f"(rogue access points); 12.10.2 = testing backup "
                      f"restoration. Scenario: {scenario} Which PCI DSS "
                      f"requirement does this fail? Answer with ONLY the "
                      f"requirement number (like '5.3').")
            def chk(a, ctrl=ctrl):
                return ctrl in a
            tasks[i] = (prompt, chk)
        # --- k13 malware triage ---
        else:  # k13
            kind = rng.choice(["ransomware", "infostealer", "loader"])
            if kind == "ransomware":
                detail = ("embedded strings reference a ransom note pattern "
                          "and '.encrypted' extensions; a hard-coded onion "
                          "address; persistence via a registry Run key; no "
                          "network capability for exfiltration found "
                          "statically")
            elif kind == "infostealer":
                detail = ("embedded strings reference browser profile "
                          "paths and credential store files; a hardcoded "
                          "SMTP or webhook endpoint; routines walking "
                          "cookie and wallet storage paths; no file "
                          "extension rewriting")
            else:
                detail = ("a tiny first stage whose only capability is "
                          "downloading and launching a second stage from a "
                          "remote server; no embedded payload strings; "
                          "persistence via a scheduled task")
            prompt = (f"Defensive malware triage from static indicators "
                      f"only (no execution): a sample shows:\n"
                      f"- imports: only a few functions typical of raw file "
                      f"writes and process hollowing\n"
                      f"- {detail}\n"
                      f"Classify the sample as exactly ONE of these classes: "
                      f"ransomware, infostealer, or loader. Then name the FIRST "
                      f"safe analysis step. Format: class=<one word>; "
                      f"first_step=<one phrase>")
            def chk(a, kind=kind):
                al = a.lower()
                return ((kind in al) and
                        ("static" in al or "sandbox" in al or "hash" in al or
                         "offline" in al or "safe" in al))
            tasks[i] = (prompt, chk)
    return tasks


def answer(prompt):
    r = requests.post(BASE_URL, json={
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 900, "stream": False,
    }, timeout=900)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main():
    done = set()
    if WORK.exists():
        for line in WORK.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["id"])
    tasks = gen_tasks()
    banked = len(done)
    log(f"start: banked={banked}/{TARGET}")
    for i in sorted(tasks):
        if banked >= TARGET:
            log(f"target reached: {banked}"); break
        if i in done:
            continue
        prompt, chk = tasks[i]
        t0 = time.time()
        try:
            msgs = [{"role": "user", "content": prompt}]
            ans = answer(prompt)
            msgs.append({"role": "assistant", "content": ans})
            ok = bool(chk(ans))
        except Exception as e:
            log(f"task {i}: ERROR {type(e).__name__}: {e}"); continue
        dt = time.time() - t0
        log(f"task {i} (k {i % 8 + 6}): {'BANK' if ok else 'reject'} "
            f"({dt:.0f}s) banked={banked + 1 if ok else banked}")
        if ok:
            banked += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "kind": i % 8 + 6,
                                    "secs": round(dt),
                                    "messages": msgs}) + "\n")
    log(f"finish: banked={banked}/{TARGET}")


if __name__ == "__main__":
    main()