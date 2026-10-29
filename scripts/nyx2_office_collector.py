# Nyx-2-Office collector harness v1 — teacher-ladder verified trajectories.
# Randomized office agent tasks (same archetypes as nyx2_base_eval.py), run
# through the TEACHER (qwen3coder-30b-A3B, port 8002) in a live sandbox with
# the terminal tool. Every trajectory is executed and VERIFIED before banking;
# only passing trajectories become training data (execution-verified only).
# Banked sample = full OpenAI-format message list + tools (student SFT can
# re-render through its own chat template).
#   .venv\Scripts\python.exe scripts\nyx2_office_collector.py
# Resumable: skips task ids already in work_office.jsonl.
import json, random, shutil, subprocess, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
SANDBOX = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\nyx2_sandbox")
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
WORK = OUT / "work_office.jsonl"
LOG = OUT / "office_log.txt"
MAX_TURNS = 8
TARGET_VERIFIED = 400
N_TASKS = 1200

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


def log(msg):
    line = f"[office] {time.strftime('%H:%M:%S')} {msg}"
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


def read(name):
    p = SANDBOX / name
    return p.read_text(encoding="utf-8", errors="replace").strip() if p.exists() else None


def has(name):
    return (SANDBOX / name).exists()


WORDS = ["alpha", "bravo", "delta", "cherry", "mango", "kiwi", "pear",
         "quince", "fig", "grape", "plum", "peach", "melon", "papaya"]
NAMES = ["report", "invoice", "ledger", "notes", "draft", "summary",
         "budget", "plan", "memo", "roster"]


def csv_setup(rng):
    n = rng.randint(5, 9)
    vals = [rng.randint(1, 99) for _ in range(n)]
    items = [f"item{i+1}" for i in range(n)]
    csv = "item,sales\n" + "\n".join(f"{it},{v}" for it, v in zip(items, vals))
    setup = [f'python -c "open(\'data.csv\',\'w\').write({csv!r})"']
    return setup, vals


# Each generator -> (setup, prompt, verifier) ; verifier closure over expected.
def gen_tasks():
    tasks = {}
    rng = random.Random(0)
    for i in range(N_TASKS):
        kind = i % 10
        if kind == 0:
            content = f"{rng.choice(WORDS)} {rng.choice(WORDS)} {rng.randint(1,99)}"
            tasks[i] = (
                None,
                f"Create a file called notes.txt containing exactly the text: {content}",
                lambda content=content: read("notes.txt") == content)
        elif kind == 1:
            setup, vals = csv_setup(rng)
            s = sum(vals)
            tasks[i] = (
                setup,
                "The file data.csv has a sales column. Compute the TOTAL sum "
                "of the sales values and write ONLY that number to total.txt",
                lambda s=s: read("total.txt") == str(s))
        elif kind == 2:
            old, new = rng.choice(NAMES) + "_old.txt", rng.choice(NAMES) + "_new.txt"
            txt = rng.choice(WORDS)
            tasks[i] = (
                [f"echo {txt}> {old}"],
                f"Rename {old} to {new}",
                lambda old=old, new=new, txt=txt:
                    (not has(old)) and read(new) == txt)
        elif kind == 3:
            k = rng.randint(3, 5)
            ws = rng.sample(WORDS, k)
            sorted_ws = sorted(ws)
            setup = [f"python -c \"open('unsorted.txt','w').write({chr(10).join(ws)!r})\""]
            tasks[i] = (
                setup,
                "Sort the lines of unsorted.txt alphabetically and save the "
                "result to sorted.txt (one word per line)",
                lambda sw=sorted_ws: read("sorted.txt") == "\n".join(sw))
        elif kind == 4:
            d = rng.choice(NAMES) + "s"
            content = rng.choice(WORDS)
            tasks[i] = (
                None,
                f"Create a directory called {d}, and inside it create a file "
                f"q4.txt containing: {content}",
                lambda d=d, content=content: read(f"{d}\\q4.txt") == content)
        elif kind == 5:
            setup, vals = csv_setup(rng)
            tasks[i] = (
                setup,
                "Count how many rows (excluding the header) data.csv has and "
                "write ONLY the number to count.txt",
                lambda n=len(vals): read("count.txt") == str(n))
        elif kind == 6:
            setup, vals = csv_setup(rng)
            avg = round(sum(vals) / len(vals), 2)
            tasks[i] = (
                setup,
                "Compute the average of the sales values in data.csv and write "
                "ONLY the result rounded to 2 decimals to avg.txt",
                lambda a=str(avg): (read("avg.txt") or "").replace(".0", ".") == a
                or read("avg.txt") in (a, f"{avg:.2f}"))
        elif kind == 7:
            first, second = rng.choice(WORDS), rng.choice(WORDS)
            tasks[i] = (
                [f"echo {first}> log.txt"],
                f"Append the line '{second}' to the existing file log.txt "
                "without removing its current content",
                lambda f=first, s=second: read("log.txt") == f"{f}\n{s}")
        elif kind == 8:
            setup, vals = csv_setup(rng)
            m = str(max(vals))
            tasks[i] = (
                setup,
                "Find the maximum sales value in data.csv and write ONLY that "
                "number to max.txt",
                lambda m=m: read("max.txt") == m)
        else:  # 9
            setup, vals = csv_setup(rng)
            t = rng.randint(10, 60)
            keep = [v for v in vals if v > t]
            exp = "item,sales\n" + "\n".join(
                f"item{i+1},{v}" for i, v in enumerate(vals) if v > t)
            tasks[i] = (
                setup,
                f"Create high.csv containing only the header and the rows "
                f"where sales is greater than {t}",
                lambda e=exp: read("high.csv") == e)
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
    log(f"start: banked={banked}/{TARGET_VERIFIED}, "
        f"done_ids={len(done_ids)}")
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
        log(f"task {i}: {'BANK' if ok else 'reject'} ({n_calls} calls, "
            f"{dt:.0f}s) banked={banked + 1 if ok else banked}")
        if ok:
            banked += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "archetype": i % 10,
                                    "tool_calls": n_calls, "secs": round(dt),
                                    "tools": [TERMINAL_TOOL],
                                    "messages": messages}) + "\n")
    log(f"finish: banked={banked}/{TARGET_VERIFIED}")


if __name__ == "__main__":
    main()