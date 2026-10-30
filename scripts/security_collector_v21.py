# Nyx-2 Security collector v2.1 — teacher-ladder VERIFIED trajectories for
# the audit/forensic domain. Randomized instances of the battery v2.1
# archetypes; ground truth is computed programmatically; the teacher's
# answer is machine-verified before banking. ALL DEFENSIVE analysis tasks.
# Banked -> work_sec21.jsonl. Run with teacher server up on :8002:
#   .venv\Scripts\python.exe scripts\security_collector_v21.py
# Resumable: skips ids already banked.
import ipaddress, json, random, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
WORK = OUT / "work_sec21.jsonl"
LOG = OUT / "sec21_collect_log.txt"
TARGET = 400
N_TASKS = 900

EXT = ["203.0.113.9", "45.9.20.101", "185.220.4.7", "91.219.4.18"]
INT = ["10.0.0.5", "10.0.0.33"]
BENIGN_UA = "Mozilla/5.0 (normal)"
WEB = ["index.html", "style.css", "assets/logo.png", "assets/app.js", "robots.txt"]


def log(msg):
    line = f"[sec21] {time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def gen_tasks():
    """(prompt, expected-substring checker) per id. Ground truth computed."""
    tasks = {}
    for i in range(N_TASKS):
        rng = random.Random(3000 + i)
        k = i % 6
        if k == 0:
            # noisy IOC: 2 malicious + 2 benign
            m1, m2 = rng.sample(EXT, 2)
            b1, b2 = f"198.51.100.{rng.randint(2, 250)}", f"192.0.2.{rng.randint(2, 250)}"
            lines = [f"{m1} - GET /.git/config 404; UA=python-requests",
                     f"{b1} - GET /{rng.choice(WEB)} 200; UA={BENIGN_UA}",
                     f"{m2} - GET /backup.sql 404; GET /.env 404",
                     f"{b2} - GET /{rng.choice(WEB)} 200; UA=Chrome mobile"]
            order = list(range(4)); rng.shuffle(order)
            prompt = ("Triage this web server log:\n" +
                      "\n".join(lines[j] for j in order) +
                      "\nWhich IPs are malicious? Answer with ONLY the malicious "
                      "IPs, comma-separated, in order of first appearance.")
            first = min(order.index(0), order.index(2))
            exp = [m1, m2] if first == order.index(0) else [m2, m1]
            def chk(a, exp=exp):
                al = a.replace(" ", "")
                return all(e in al for e in exp) and (
                    al.index(exp[0]) < al.index(exp[1]))
            tasks[i] = (prompt, chk)
        elif k == 1:
            # pivot chain: entry -> hop1 -> hop2 -> exfil
            entry = rng.choice(INT)
            hop1 = f"172.16.{rng.randint(1, 30)}.{rng.randint(2, 250)}"
            hop2 = f"172.16.{rng.randint(31, 60)}.{rng.randint(2, 250)}"
            exfil = rng.choice(EXT)
            prompt = (f"Incident reconstruction. Logs:\n"
                      f"fw.log: {entry} -> {hop1}:445 ALLOW (only external->internal SMB hit today)\n"
                      f"{hop1} (file server) auth.log: new local admin 'svc_backup' created\n"
                      f"{hop1} -> {hop2}:3389 ALLOW (first ever east-west RDP from file server)\n"
                      f"{hop2} (db server): mysqldump --all-databases observed\n"
                      f"fw.log: {hop2} -> {exfil}:443 ALLOW (first outbound to that ASN)\n"
                      f"State the FULL chain using EXACTLY this format, one line:\n"
                      f"entry=<ip>; hop1=<ip>; hop2=<ip>; exfil=<ip>")
            def chk(a, e=(entry, hop1, hop2, exfil)):
                return all(x in a for x in e)
            tasks[i] = (prompt, chk)
        elif k == 2:
            # webshell find (described, no literals)
            bad = rng.choice(["uploads/favicon.php", "uploads/cache.php",
                               "static/health.php", "images/thumb.php"])
            good = [f"{p}" for p in ("index.php", "contact.php", "about.php")]
            prompt = ("Post-compromise web audit: which file is the likely webshell?\n" +
                      "\n".join(f"/var/www/html/{g} - last modified 2025-11-02 (matches deploy)" for g in good) +
                      f"\n/var/www/html/{bad} - 47 bytes, modified TODAY, owner www-data, "
                      "content is a single line that evaluates arbitrary data sent in an "
                      "HTTP POST parameter (a classic one-line webshell pattern)\n"
                      "/var/www/html/robots.txt - modified 2025-11-02\n"
                      "Answer with ONLY the file path.")
            tasks[i] = (prompt, lambda a, b=bad: b in a)
        elif k == 3:
            # ACL audit
            user = rng.choice(["dave", "maya", "sam", "kate", "liam"])
            res = rng.choice(["Full Control", "Modify", "Write"])
            prompt = (f"File server audit (Windows). Share \\\\FS01\\Finance ACEs:\n"
                      "FinanceUsers: Modify (inherited)\n"
                      "Everyone: Read (root only, inherited)\n"
                      f"DOMAIN\\{user}: {res} (NOT inherited, added 3 days ago, applies to "
                      "ThisFolderSubfoldersAndFiles)\n"
                      "Which ACE is the audit finding and what is the risk? Format (one "
                      f"line): principal=<who>; risk=<one phrase>.")
            def chk(a, u=user, r=res):
                return u in a.lower() and ("over" in a.lower() or "privileg" in a.lower()
                                           or r.lower() in a.lower() or "broad" in a.lower())
            tasks[i] = (prompt, chk)
        elif k == 4:
            # beacon cadence
            host = rng.choice(INT)
            c2 = rng.choice(EXT)
            times = [rng.randint(140, 200)]
            for _ in range(4):
                times.append(times[-1] + rng.randint(155, 170))
            prompt = (f"IDS alert review (defensive): outbound TLS from {host} to {c2} "
                      "shows 22 connections in 1 hour, inter-arrival times: " +
                      ", ".join(f"{t-int(times[0])}s" if False else f"{t - times[0]}s"
                                for t in times[1:]) +
                      " — near-constant with small jitter, regardless of business hours. "
                      "What behavior class is this and what is the giveaway? Format (one "
                      "line): class=<one word>; giveaway=<one phrase>.")
            def chk(a):
                return ("beacon" in a.lower() or "c2" in a.lower()) and (
                    "regular" in a.lower() or "constant" in a.lower()
                    or "interval" in a.lower() or "periodic" in a.lower()
                    or "jitter" in a.lower())
            tasks[i] = (prompt, chk)
        else:  # k == 5
            # SIEM correlation: 3 related + 1 noise
            h = f"WS-{rng.randint(10, 99)}"
            u = rng.choice(["maya", "ben", "anna", "kyle"])
            noise = f"09:{rng.randint(30, 45):02d}"
            prompt = (f"Correlate these alerts into ONE incident (timeline):\n"
                      f"09:12 AV: doc.exe quarantined on host {h}\n"
                      f"09:13 EDR: doc.exe dropped by winword.exe on host {h}\n"
                      f"09:14 FW: host {h} -> {rng.choice(EXT)}:443 new\n"
                      f"{noise} Auth: unrelated user 'zz_other' failed VPN login from a different site\n"
                      "Which alerts belong to the SAME incident and which is unrelated noise? "
                      "Format: incident=<timestamps comma-separated>; noise=<timestamp>.")
            def chk(a, n=noise):
                return ("09:12" in a and "09:13" in a and "09:14" in a and
                        n in a and ("noise" in a.lower() or "unrelated" in a.lower()))
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
        log(f"task {i} (k {i % 6}): {'BANK' if ok else 'reject'} "
            f"({dt:.0f}s) banked={banked + 1 if ok else banked}")
        if ok:
            banked += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "kind": i % 6, "secs": round(dt),
                                    "messages": msgs}) + "\n")
    log(f"finish: banked={banked}/{TARGET}")


if __name__ == "__main__":
    main()