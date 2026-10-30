# Nyx-2-Office collector v2 — BROAD real-life office archetypes.
# v1 (nyx2_office_collector.py) covered 10 file/CSV archetypes. v2 adds 12
# real-office archetypes (scheduling, receptionist, email, phone messages,
# search, merge, dedupe, mail-merge, inventory, filing, minutes, reports).
# Same verified-trajectory design: teacher executes, verifier checks, only
# passing trajectories are banked -> work_office_v2.jsonl (fresh id space).
#   spark-venv or .venv (needs requests):
#   .venv\Scripts\python.exe scripts\nyx2_office_collector_v2.py
# Resumable: skips ids already in work_office_v2.jsonl.
import json, random, shutil, subprocess, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
SANDBOX = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\nyx2_sandbox")
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
WORK = OUT / "work_office_v2.jsonl"
LOG = OUT / "office_v2_log.txt"
MAX_TURNS = 8
TARGET_VERIFIED = 400
N_TASKS = 1400

TERMINAL_TOOL = {
    "type": "function",
    "function": {
        "name": "terminal",
        "description": ("Run a shell command on this Windows machine in the "
                        "current working directory and return its output."),
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"}},
                       "required": ["command"]},
    },
}

SYS = ("You are a precise office-assistant agent with a terminal tool. "
       "Complete the user's task exactly. Prefer writing files with python "
       "one-liners or echo. Be concise.")

FIRST = ["anna", "ben", "cara", "david", "ella", "fay", "gus", "hana",
         "ivan", "june", "kyle", "lila", "omar", "nina", "paul", "rita"]
LAST = ["smith", "jones", "lee", "brown", "nguyen", "patel", "ross",
        "kaur", "chen", "diaz"]
HOURS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30)]


def log(msg):
    line = f"[office-v2] {time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=SANDBOX, capture_output=True,
                           text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
        return out.strip()[:2000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "(timeout)"


def py(content, name):
    return f"python -c \"open({name!r},'w',encoding='utf-8').write({content!r})\""


def read(name):
    p = SANDBOX / name
    return p.read_text(encoding="utf-8", errors="replace").strip() if p.exists() else None


def has(name):
    return (SANDBOX / name).exists()


def read_raw(name):
    p = SANDBOX / name
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


# kind 10: appointment booking
def t_schedule(rng):
    times = rng.sample(HOURS, 4)
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    header = "time,client\n"
    setup = [py(header, "schedule.txt")]
    prompt = (f"The reception schedule for tomorrow is in schedule.txt "
              f"(header: time,client). Book an appointment for {name} "
              f"at {times[0]} by adding a new row with the time and client "
              f"name. Do not change anything else.")
    exp = header + f"{times[0]},{name}"
    return setup, prompt, lambda e=exp: read("schedule.txt") == e


# kind 11: visitor log (receptionist)
def t_visitor(rng):
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    visiting = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    tm = rng.choice(HOURS)
    header = "time,visitor,visiting\n"
    setup = [py(header, "visitors.csv")]
    prompt = (f"A visitor named {name} has arrived to see {visiting}. Record "
              f"this in visitors.csv (header: time,visitor,visiting) with "
              f"today's arrival time noted as {tm}.")
    exp = header + f"{tm},{name},{visiting}"
    return setup, prompt, lambda e=exp: read("visitors.csv") == e


# kind 12: email draft
def t_email(rng):
    to = f"{rng.choice(FIRST)}.{rng.choice(LAST)}@corp.example"
    subj = f"Q{rng.randint(1,4)} {rng.choice(['report', 'invoice', 'summary', 'plan'])} ready"
    body = f"Please find the {rng.choice(['attached','enclosed'])} document. Kind regards."
    prompt = (f"Create a file email.txt containing an email draft with EXACTLY "
              f"three sections on separate lines:\nTo: {to}\nSubject: {subj}\n"
              f"then a blank line, then the body:\n{body}")
    def v(to=to, subj=subj, body=body):
        t = read_raw("email.txt")
        return (f"To: {to}" in t and f"Subject: {subj}" in t and body in t)
    return None, prompt, v


# kind 13: search/extract lines
def t_search(rng):
    kw = rng.choice(["urgent", "payment", "meeting", "delivery", "invoice"])
    lines = [f"note about {rng.choice(['routine','urgent','other'])} item {i}"
             for i in range(1, 9)]
    setup = [py("\n".join(lines), "log.txt")]
    prompt = (f"Find all lines in log.txt that contain the word '{kw}' and "
              f"write ONLY those lines, in their original order, to results.txt "
              f"(one per line, no blank lines).")
    exp = "\n".join(l for l in lines if kw in l)
    return setup, prompt, lambda e=exp: read("results.txt") == e


# kind 14: merge two CSVs
def t_merge(rng):
    h = "item,qty\n"
    a = [f"a{i},{rng.randint(1,20)}" for i in range(1, 4)]
    b = [f"b{i},{rng.randint(1,20)}" for i in range(1, 4)]
    setup = [py(h + "\n".join(a), "a.csv"), py(h + "\n".join(b), "b.csv")]
    prompt = ("Combine a.csv and b.csv into combined.csv: keep the single "
              "header row, then all rows of a.csv followed by all rows of "
              "b.csv.")
    exp = h + "\n".join(a + b)
    return setup, prompt, lambda e=exp: read("combined.csv") == e


# kind 15: dedupe
def t_dedupe(rng):
    pool = [f"{rng.choice(FIRST)} {rng.choice(LAST)}".title() for _ in range(10)]
    names = pool + rng.sample(pool, 3)
    rng.shuffle(names)
    setup = [py("\n".join(names), "names.txt")]
    prompt = ("Remove duplicate lines from names.txt and write the unique "
              "names to unique.txt, keeping the FIRST occurrence of each "
              "name in its original order (one per line).")
    seen, exp = [], set()
    for n in names:
        if n not in exp:
            exp.add(n); seen.append(n)
    e = "\n".join(seen)
    return setup, prompt, lambda e=e: read("unique.txt") == e


# kind 16: mail-merge letter
def t_letter(rng):
    person = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    body = f"Your appointment has been confirmed for {rng.choice(HOURS)}."
    prompt = (f"Create letter.txt containing EXACTLY this text, with NAME "
              f"replaced by {person}:\nDear NAME,\n{body}\nSincerely,\n"
              f"The Office")
    exp = f"Dear {person},\n{body}\nSincerely,\nThe Office"
    return None, prompt, lambda e=exp: read("letter.txt") == e


# kind 17: inventory reorder
def t_inventory(rng):
    n = 6
    items = [f"item{i+1}" for i in range(n)]
    qtys = [rng.randint(0, 12) for _ in range(n)]
    thr = 4
    csv = "item,qty\n" + "\n".join(f"{it},{q}" for it, q in zip(items, qtys))
    setup = [py(csv, "inventory.csv")]
    prompt = (f"inventory.csv lists item,qty. Write to reorder.txt the names "
              f"of all items with qty less than {thr}, one per line, in file "
              f"order, with no header.")
    exp = "\n".join(it for it, q in zip(items, qtys) if q < thr)
    return setup, prompt, (lambda e=exp: read("reorder.txt") == e) if exp else None


# kind 18: filing / archive move
def t_archive(rng):
    k = 3
    files = [f"invoice{rng.randint(100,999)}.txt" for _ in range(k)]
    other = [f"note{rng.randint(100,999)}.txt" for _ in range(2)]
    setup = [f"echo x> {f}" for f in files + other]
    prompt = ("Create a directory called archive and MOVE every file whose "
              "name starts with 'invoice' into it. Other files stay in the "
              "current directory.")
    def v(files=files, other=other):
        return (all(has(f"archive\\{f}") and not has(f) for f in files)
                and all(has(f) for f in other))
    return setup, prompt, v


# kind 19: phone message
def t_phone(rng):
    caller = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    num = f"04{rng.randint(10,99)} {rng.randint(100,999)} {rng.randint(100,999)}"
    tm = rng.choice(HOURS)
    for_ = f"{rng.choice(FIRST)} {rng.choice(LAST)}".title()
    prompt = (f"Take a phone message. Create message_for_{for_.split()[0].lower()}.txt "
              f"containing EXACTLY these lines:\nCaller: {caller}\n"
              f"Time: {tm}\nNumber: {num}\nMessage: Please call back today.")
    fname = f"message_for_{for_.split()[0].lower()}.txt"
    exp = f"Caller: {caller}\nTime: {tm}\nNumber: {num}\nMessage: Please call back today."
    return None, prompt, lambda fn=fname, e=exp: read(fn) == e


# kind 20: meeting minutes
def t_minutes(rng):
    ds = [f"Approve the {rng.choice(['budget','plan','report'])}",
          f"Schedule review for {rng.choice(['Monday','Friday'])}",
          f"Assign {rng.choice(FIRST).title()} as lead"]
    setup = [py("\n".join(ds), "bullets.txt")]
    prompt = ("bullets.txt lists three decisions taken in a meeting. Create "
              "minutes.txt that starts with the line 'Meeting Minutes', then "
              "a blank line, then the three decisions numbered 1. 2. 3., one "
              "per line, exactly as written in bullets.txt.")
    exp = "Meeting Minutes\n\n" + "\n".join(f"{i+1}. {d}" for i, d in enumerate(ds))
    return setup, prompt, lambda e=exp: read("minutes.txt") == e


# kind 21: report generation
def t_report(rng):
    n = rng.randint(5, 8)
    vals = [rng.randint(1, 99) for _ in range(n)]
    csv = "item,sales\n" + "\n".join(f"item{i+1},{v}" for i, v in enumerate(vals))
    setup = [py(csv, "data.csv")]
    prompt = ("From data.csv write report.txt with EXACTLY two lines:\n"
              f"Total: {sum(vals)}\nCount: {n}")
    exp = f"Total: {sum(vals)}\nCount: {n}"
    return setup, prompt, lambda e=exp: read("report.txt") == e


GENS = [t_schedule, t_visitor, t_email, t_search, t_merge, t_dedupe,
        t_letter, t_inventory, t_archive, t_phone, t_minutes, t_report]


def gen_tasks():
    tasks = {}
    for i in range(N_TASKS):
        rng = random.Random(1000 + i)
        g = GENS[i % len(GENS)](rng)
        if g is None:      # e.g. empty reorder list
            continue
        tasks[i] = g
    return tasks


def agent_task(prompt, setup=None):
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)
    for cmd in (setup or []):
        run_cmd(cmd)
    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": prompt}]
    tool_calls_n = 0
    for _ in range(MAX_TURNS):
        r = requests.post(BASE_URL, json={
            "messages": messages, "tools": [TERMINAL_TOOL],
            "temperature": 0.2, "max_tokens": 1500, "stream": False,
        }, timeout=900)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        messages.append({"role": "assistant",
                         "content": msg.get("content") or "",
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            break
        for tc in calls:
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            tool_calls_n += 1
            out = run_cmd(args.get("command", ""))
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": out})
    return messages, tool_calls_n


def main():
    done_ids = set()
    if WORK.exists():
        for line in WORK.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done_ids.add(json.loads(line)["id"])
    tasks = gen_tasks()
    banked = len(done_ids)
    log(f"start: banked={banked}/{TARGET_VERIFIED}, done_ids={len(done_ids)}")
    for i in sorted(tasks):
        if banked >= TARGET_VERIFIED:
            log(f"target reached: {banked} verified"); break
        if i in done_ids:
            continue
        setup, prompt, verify = tasks[i]
        t0 = time.time()
        try:
            messages, n_calls = agent_task(prompt, setup)
        except Exception as e:
            log(f"task {i}: ERROR {type(e).__name__}: {e}"); continue
        ok = False
        try:
            ok = bool(verify())
        except Exception:
            ok = False
        dt = time.time() - t0
        log(f"task {i} (kind {i % 12}): {'BANK' if ok else 'reject'} "
            f"({n_calls} calls, {dt:.0f}s) banked={banked + 1 if ok else banked}")
        if ok:
            banked += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "archetype": i % 12,
                                    "tool_calls": n_calls, "secs": round(dt),
                                    "tools": [TERMINAL_TOOL],
                                    "messages": messages}) + "\n")
    log(f"finish: banked={banked}/{TARGET_VERIFIED}")


if __name__ == "__main__":
    main()