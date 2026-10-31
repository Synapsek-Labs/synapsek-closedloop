# Nyx-2 base capability audit — Spark-X2.6-1.7B on office + security agent tasks.
# Measures the BASE model through the real agent loop (terminal tool, live
# filesystem sandbox) per the failure-band law: trainable headroom = 40-70%.
# Run on shinobi (uses the local spark server at 127.0.0.1:8001):
#   spark-venv python scripts/nyx2_base_eval.py
import json, os, shutil, subprocess, sys, time, re
from pathlib import Path
import os
import requests

BASE_URL = "http://127.0.0.1:8001/v1/chat/completions"
SANDBOX = Path(os.environ.get(
    "NYX_SANDBOX",
    r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1\nyx2_sandbox",
))
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
MAX_TURNS = 8

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

SYS = ("You are a precise office-assistant agent with a terminal tool on "
       "Windows (cmd.exe). Complete the user's task exactly. IMPORTANT: cmd "
       "echo does NOT interpret \\n — never use 'echo -e'. To write "
       "multi-line files use a python one-liner (python -c with \\n "
       "escapes) or several 'echo ... >> file' commands. When a python -c "
       "one-liner hits quoting issues, build the script with multiple "
       "'echo ... >> script.py' lines and then run 'python script.py'. "
       "Be concise.")


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=SANDBOX, capture_output=True,
                           text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
        return out.strip()[:2000] or "(no output)", r.returncode
    except subprocess.TimeoutExpired:
        return "(timeout)", 1


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
        }, timeout=600)
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
            out, _ = run_cmd(args.get("command", ""))
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": out})
    return tool_calls_n


def read(name):
    p = SANDBOX / name
    return p.read_text(encoding="utf-8", errors="replace").strip() if p.exists() else None


def has(name):
    return (SANDBOX / name).exists()


# ---------------- Office battery (filesystem-verifiable) ----------------
CSV = "\n".join(["item,sales"] +
               [f"item{i},{v}" for i, v in enumerate([12, 7, 25, 3, 18, 40, 9], 1)])

OFFICE = [
    ("notes", None,
     "Create a file called notes.txt containing exactly the text: hello world",
     lambda: read("notes.txt") == "hello world"),
    ("sum", [f"echo {CSV}> data.csv"],
     "The file data.csv has a sales column. Compute the TOTAL sum of the "
     "sales values and write ONLY that number to total.txt",
     lambda: read("total.txt") == "114"),
    ("rename", ["echo aaa> old_name.txt"],
     "Rename old_name.txt to new_name.txt",
     lambda: (not has("old_name.txt")) and read("new_name.txt") == "aaa"),
    ("sort", ["echo banana> unsorted.txt", "echo apple>> unsorted.txt",
              "echo cherry>> unsorted.txt"],
     "Sort the lines of unsorted.txt alphabetically and save the result to "
     "sorted.txt (one word per line)",
     lambda: read("sorted.txt") == "apple\nbanana\ncherry"),
    ("mkdir", None,
     "Create a directory called reports, and inside it create a file "
     "q4.txt containing: done",
     lambda: read("reports\\q4.txt") == "done"),
    ("count", [f"echo {CSV}> data.csv"],
     "Count how many rows (excluding the header) data.csv has and write "
     "ONLY the number to count.txt",
     lambda: read("count.txt") == "7"),
    ("avg", [f"echo {CSV}> data.csv"],
     "Compute the average of the sales values in data.csv and write ONLY "
     "the result rounded to 2 decimals to avg.txt",
     lambda: read("avg.txt") in ("16.29", "16.28571")),
    ("append", ["echo first> log.txt"],
     "Append the line 'second' to the existing file log.txt without "
     "removing its current content",
     lambda: read("log.txt") == "first\nsecond"),
    ("max", [f"echo {CSV}> data.csv"],
     "Find the maximum sales value in data.csv and write ONLY that number "
     "to max.txt",
     lambda: read("max.txt") == "40"),
    ("filter", [f"echo {CSV}> data.csv"],
     "Create high.csv containing only the header and the rows where sales "
     "is greater than 15",
     lambda: (lambda rows: rows is not None and
             all(int(l.split(",")[1]) > 15
                 for l in rows.splitlines()[1:] if l.strip()))
             (read("high.csv"))),
]

# ------------- Security battery (defensive triage, exact-answer) ----------
SEC_LOG = """10.0.0.5 - login user=admin ok
10.0.0.9 - login user=admin fail
10.0.0.9 - login user=admin fail
10.0.0.9 - login user=admin fail
10.0.0.9 - login user=admin fail
10.0.0.7 - GET /index.html 200
10.0.0.31 - GET /wp-admin 403
10.0.0.31 - POST /wp-login.php 200
10.0.0.99 - GET /.env 404
10.0.0.31 - GET /wp-admin 200"""

SECURITY = [
    ("bruteforce",
     f"Security log:\n{SEC_LOG}\nWhich IP shows a brute-force login "
     "pattern? Answer with ONLY the IP address.",
     "10.0.0.9"),
    ("admin_takeover",
     f"Security log:\n{SEC_LOG}\nAfter failing several logins, one IP "
     "later gets a 200 on the admin page. Which IP likely compromised the "
     "admin account? Answer with ONLY the IP address.",
     "10.0.0.31"),
    ("probe",
     f"Security log:\n{SEC_LOG}\nWhich IP is probing for exposed "
     "environment/config files? Answer with ONLY the IP address.",
     "10.0.0.99"),
    ("severity",
     "Rank these findings by severity (highest first): A) phone number "
     "in metadata, B) SQL injection in login form, C) version banner in "
     "footer. Answer with only the letters, like 'B,A,C'.",
     None),  # expected: B,C,A or B,A,C — checked loosely
    ("xss",
     "A guestbook page renders user comments without encoding. Which "
     "vulnerability class is this? Answer with the acronym only.",
     "xss"),
    ("port",
     "You must secure an SSH server. Is it safer to expose it on port "
     "22 with password auth, or a nonstandard port with key-only auth? "
     "Answer with one word: 'key' or 'password'.",
     "key"),
]


def text_task(prompt):
    r = requests.post(BASE_URL, json={
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 800, "stream": False,
    }, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main():
    results = {"office": {}, "security": {}}
    for name, setup, prompt, check in OFFICE:
        t0 = time.time()
        n_calls = agent_task(prompt, setup)
        ok = bool(check())
        results["office"][name] = {"pass": ok, "tool_calls": n_calls,
                                   "secs": round(time.time() - t0, 1)}
        print(f"[office:{name}] {'PASS' if ok else 'FAIL'} "
              f"({n_calls} calls, {results['office'][name]['secs']}s)",
              flush=True)
    for name, prompt, expected in SECURITY:
        ans = text_task(prompt).lower()
        if name == "severity":
            ok = re.sub(r"[^bca]", "", ans)[:3] in ("bca", "bac")
        else:
            ok = expected in ans
        results["security"][name] = {"pass": bool(ok), "answer": ans[:200]}
        print(f"[sec:{name}] {'PASS' if ok else 'FAIL'}: {ans[:120]}",
              flush=True)

    o = sum(v["pass"] for v in results["office"].values())
    s = sum(v["pass"] for v in results["security"].values())
    summary = {
        "model": "spark-x2.6-1.7b (base)",
        "office_acc": o / len(OFFICE),
        "security_acc": s / len(SECURITY),
        "office_n": len(OFFICE), "security_n": len(SECURITY),
        "verdict": "MEASURE base for failure band: trainable if 0.40-0.70",
        "detail": results,
    }
    (OUT / "nyx2_base_audit.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                     ("model", "office_acc", "security_acc")},
                    indent=2), flush=True)


if __name__ == "__main__":
    main()
