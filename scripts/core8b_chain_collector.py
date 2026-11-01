# Core 8B HARD-AGENT chain collector — execution-verified multi-step trajectories.
# Pre-registered per docs/CORE8B_PREREGISTRATION.md (base composite 0.95 => HARD data only).
# Each instance: parameterized multi-step task, sandbox setup, teacher solves via terminal
# tool loop (qwen3coder-30b :8002), END-STATE verified deterministically. Banks full
# trajectory (user task, tool calls+results, final answer). TARGET 800 banked rows.
# Bars for the eventual gate (frozen): G1-hard >=8/10, G2-hard >=14/20, G3 chains >=7/10.
import json, os, random, shutil, subprocess, sys, time
from pathlib import Path
import requests

BASE_URL = os.environ.get("TEACHER_URL", "http://127.0.0.1:8002/v1/chat/completions")
NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
SBX = Path(os.environ.get("CORE8B_SANDBOX", str(NODE / "core8b_sbx")))
OUT = NODE / "work_core8b_chains.jsonl"
TARGET = int(os.environ.get("CORE8B_TARGET", "800"))
MAX_TURNS = 12

TERMINAL_TOOL = {"type": "function", "function": {
    "name": "terminal",
    "description": "Run a shell command on Windows (cmd.exe) in the sandbox cwd. Returns output.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                  "required": ["command"]}}}

SYS = ("You are an expert engineering agent with a terminal tool on Windows cmd.exe. "
       "Complete the user's multi-step task exactly. Prefer python one-liners "
       "(python -c) for computation. Be efficient: few commands, exact results. "
       "When done, reply with a single line starting FINAL: summarizing the outcome.")

def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, shell=True, cwd=SBX, capture_output=True, text=True, timeout=60)
        return ((r.stdout or "") + (r.stderr or "")).strip()[:1500] or "(no output)", r.returncode
    except Exception as e:
        return f"(error {e})", 1

# ---------------- chain families: setup() then verify() end-state ----------------
def csv_rows(n, seed):
    rng = random.Random(seed)
    rows = ["id,region,units,price"]
    regions = ["nsw", "vic", "qld", "wa"]
    for i in range(n):
        rows.append(f"{i},{rng.choice(regions)},{rng.randint(1,40)},{rng.randint(10,99)}")
    return "\n".join(rows)

def mk(seed):
    rng = random.Random(seed)
    fam = seed % 8
    setup, task, verify = [], "", None
    if fam == 0:  # multi-step CSV analytics pipeline
        data = csv_rows(rng.randint(8, 14), seed)
        setup = [f'python -c "open(\'sales.csv\',\'w\').write({data!r})"']
        reg = rng.choice(["nsw", "vic", "qld"])
        task = (f"In sales.csv: compute TOTAL revenue (units*price summed over all rows) "
                f"and the number of rows where region={reg}. Write two files: total.txt "
                f"containing ONLY the integer total, and count.txt containing ONLY the count.")
        def verify():
            try:
                lines = [l for l in open(SBX / "sales.csv").read().splitlines()[1:] if l.strip()]
                tot = sum(int(l.split(",")[2]) * int(l.split(",")[3]) for l in lines)
                cnt = sum(1 for l in lines if l.split(",")[1] == reg)
                return (open(SBX / "total.txt").read().strip() == str(tot)
                        and open(SBX / "count.txt").read().strip() == str(cnt))
            except Exception:
                return False
    elif fam == 1:  # restructure + report
        names = [f"doc{rng.randint(1,99)}.txt" for _ in range(5)]
        setup = [f'echo {n[:-4]} data> {n}' for n in names]
        task = ("Create directory 'archive'. Move every doc*.txt file into it. Then create "
                "archive/manifest.txt listing the moved filenames one per line, sorted alphabetically.")
        def verify():
            try:
                p = SBX / "archive"
                man = [l.strip() for l in open(p / "manifest.txt").read().splitlines() if l.strip()]
                moved = sorted(x.name for x in p.glob("doc*.txt"))
                return (not (list((SBX).glob("doc*.txt"))) and man == moved
                        and len(moved) == 5)
            except Exception:
                return False
    elif fam == 2:  # merge + dedupe + sort
        a = "\n".join(sorted({f"key{rng.randint(1,30)}" for _ in range(10)}))
        b = "\n".join(sorted({f"key{rng.randint(1,30)}" for _ in range(10)}))
        setup = [f'python -c "open(\'a.txt\',\'w\').write({a!r})"',
                 f'python -c "open(\'b.txt\',\'w\').write({b!r})"']
        task = ("Merge a.txt and b.txt into merged.txt with all unique lines, sorted "
                "alphabetically, one per line. Then write n.txt containing ONLY the number "
                "of unique lines.")
        def verify():
            try:
                u = sorted({*open(SBX/"a.txt").read().split(), *open(SBX/"b.txt").read().split()})
                return (open(SBX/"merged.txt").read().split() == u
                        and open(SBX/"n.txt").read().strip() == str(len(u)))
            except Exception:
                return False
    elif fam == 3:  # config transform with validation
        port = rng.randint(1000, 9999)
        setup = [f'python -c "open(\'app.cfg\',\'w\').write(\'host=localhost\\nport=8080\\ndebug=false\\n\')"']
        task = (f"In app.cfg: change port to {port}, set debug to true, keep host unchanged. "
                "Then create check.txt containing ONLY 'OK' if the file now has exactly 3 "
                "lines and no duplicates, else 'BAD'.")
        def verify():
            try:
                d = dict(l.strip().split("=") for l in open(SBX/"app.cfg").read().splitlines() if l.strip())
                return (d.get("port") == str(port) and d.get("debug") == "true"
                        and d.get("host") == "localhost"
                        and open(SBX/"check.txt").read().strip() == "OK")
            except Exception:
                return False
    elif fam == 4:  # log analysis pipeline
        ips = [f"10.0.0.{rng.randint(2,250)}" for _ in range(4)]
        logs = []
        for i in range(20):
            logs.append(f"{ips[i % 2 if i < 10 else 3]} POST /login {'200' if i % 4 else '401'}")
        setup = [f'python -c "open(\'auth.log\',\'w\').write({chr(10).join(logs)!r})"']
        task = ("In auth.log: find the IP with the MOST 401 responses. Write top.txt with "
                "ONLY that IP. Write fails.txt with ONLY the count of 401 lines for that IP.")
        def verify():
            try:
                from collections import Counter
                c = Counter(l.split()[0] for l in open(SBX/"auth.log").read().splitlines() if " 401" in l)
                ip, n = c.most_common(1)[0]
                return (open(SBX/"top.txt").read().strip() == ip
                        and open(SBX/"fails.txt").read().strip() == str(n))
            except Exception:
                return False
    elif fam == 5:  # multi-file aggregation
        setup = []
        for i in range(3):
            vals = [str(rng.randint(1, 100)) for _ in range(rng.randint(4, 9))]
            setup.append(f"python -c \"open('d{i}.txt','w').write({repr(chr(10).join(vals))})\"")
        task = ("d1.txt, d2.txt, d3.txt each contain numbers one per line. Compute the "
                "overall MAX and overall MIN across all three files. Write max.txt with "
                "ONLY the max and min.txt with ONLY the min.")
        def verify():
            try:
                allv = [int(x) for i in range(3) for x in open(SBX/f"d{i}.txt").read().split()]
                return (open(SBX/"max.txt").read().strip() == str(max(allv))
                        and open(SBX/"min.txt").read().strip() == str(min(allv)))
            except Exception:
                return False
    elif fam == 6:  # rename pattern + count condition
        setup = [f"echo x> file_{i}.log" for i in range(rng.randint(5, 9))]
        task = ("Rename all file_*.log files to .bak extension (same base name). Then "
                "write count_bak.txt containing ONLY how many .bak files exist now.")
        def verify():
            try:
                bak = list(SBX.glob("file_*.bak"))
                logs = list(SBX.glob("file_*.log"))
                return (not logs and open(SBX/"count_bak.txt").read().strip() == str(len(bak)))
            except Exception:
                return False
    else:  # 7: word-level transform pipeline
        words = [rng.choice(["alpha","beta","gamma","delta","eps","zeta","eta"]) for _ in range(12)]
        setup = [f"python -c \"open('words.txt','w').write({repr(chr(10).join(words))})\""]
        w = rng.choice(words)
        task = (f"In words.txt: find all lines equal to '{w}'. Write matches.txt with those "
                f"lines in original order, and freq.txt with ONLY the count.")
        def verify():
            try:
                src = open(SBX/"words.txt").read().splitlines()
                exp = [x for x in src if x == w]
                return (open(SBX/"matches.txt").read().splitlines() == exp
                        and open(SBX/"freq.txt").read().strip() == str(len(exp)))
            except Exception:
                return False
    return setup, task, verify

def solve(task, setup):
    if SBX.exists():
        shutil.rmtree(SBX)
    SBX.mkdir(parents=True)
    for c in setup:
        run_cmd(c)
    messages = [{"role": "system", "content": SYS},
                {"role": "user", "content": task}]
    traj = []
    for _ in range(MAX_TURNS):
        r = requests.post(BASE_URL, json={"messages": messages, "tools": [TERMINAL_TOOL],
                                          "temperature": 0.3, "max_tokens": 1200,
                                          "stream": False}, timeout=600)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        messages.append({"role": "assistant", "content": content,
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            break
        for tc in calls:
            args = tc["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            out, _ = run_cmd(args.get("command", ""))
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
            traj.append({"tool": "terminal", "command": args.get("command", ""),
                         "result_head": out[:120]})
    return messages, traj

def main():
    banked = 0
    seed = 0
    log = open(NODE / "core8b_chain_log.txt", "a", encoding="utf-8")
    def p(s):
        print(s, flush=True); log.write(s + "\n"); log.flush()
    while banked < TARGET and seed < TARGET * 4:
        setup, task, verify = mk(seed)
        seed += 1
        try:
            messages, traj = solve(task, setup)
            ok = verify()
        except Exception as e:
            p(f"[c8b] seed {seed}: error {type(e).__name__} {e}")
            continue
        if ok and len(traj) >= 2:
            row = {"id": banked, "fam": (seed - 1) % 8, "n_steps": len(traj),
                   "messages": messages, "secs": 0}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            banked += 1
            p(f"[c8b] seed {seed}: BANK (steps={len(traj)}) banked={banked}")
        else:
            p(f"[c8b] seed {seed}: reject (verify_fail steps={len(traj)})")
    p(f"finish: banked={banked}/{TARGET}")

if __name__ == "__main__":
    main()
