# Core 8B CYCLE-2 collector — execution-verified, typed tools, MT, benign-heavy, format-clean.
# Pre-registered per synapsek-internal/research/CYCLE2_CORPUS_SPEC.md (2026-11-10, FROZEN).
#   spark-venv\Scripts\python.exe scripts\core8b_cycle2_collector.py   (teacher on :8002)
# 12 families: cycle-1's 8 chains (0-7) + audit-vuln(8) + audit-benign(9) +
# messy-config(10) + revision(11). Even seeds get a phase-2 follow-up (MT).
# Bank gate: verify OK, >=2 tool steps, format-clean. Rejects logged for diagnosis.
import json, os, random, shutil, subprocess, sys, time, re
from pathlib import Path
import requests

BASE_URL = os.environ.get("TEACHER_URL", "http://127.0.0.1:8002/v1/chat/completions")
NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
SBX = Path(os.environ.get("CYCLE2_SANDBOX", str(NODE / "cycle2_sbx")))
OUT = NODE / "work_core8b_cycle2.jsonl"
REJECT_LOG = NODE / "cycle2_rejects.jsonl"
TARGET = int(os.environ.get("CYCLE2_TARGET", "400"))
MAX_TURNS = 14

# ---- C1: TYPED tools, live-style schemas (defaults, enums, optional params) ----
TOOLS = [
    {"type": "function", "function": {
        "name": "terminal",
        "description": "Run a shell command on Windows (cmd.exe) in the sandbox cwd.",
        "parameters": {"type": "object",
                       "properties": {"command": {"type": "string"},
                                       "timeout_s": {"type": "integer", "default": 60}},
                       "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file from the sandbox. Returns its content.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                       "encoding": {"type": "string", "enum": ["utf-8", "latin-1"],
                                                    "default": "utf-8"},
                                       "max_bytes": {"type": "integer", "default": 20000}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Overwrite a text file in the sandbox with the given content.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                       "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "List entries of a sandbox directory, one per line.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string", "default": "."}},
                       "required": []}}},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search files under a sandbox directory for a literal string. "
                      "Results may include noisy unrelated matches (live-style).",
        "parameters": {"type": "object",
                       "properties": {"query": {"type": "string"},
                                       "path": {"type": "string", "default": "."},
                                       "case_sensitive": {"type": "boolean", "default": True}},
                       "required": ["query"]}}},
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
SYS = ("You are an expert engineering agent with typed tools (terminal, read_file, "
       "write_file, list_dir, search_files) on Windows. Complete the user's task "
       "exactly. Be efficient: few calls, exact results. When the task is fully done, "
       "reply with a single line starting FINAL: summarizing the outcome.")

# ---- C5: format-clean check on banked assistant content ----
FENCE_RE = re.compile(r"```")
THINK_RE = re.compile(r"<think|thought[:_ ]|let me ", re.IGNORECASE)

def run_tool(name, args):
    """Execute one typed tool call against the sandbox. C2: outputs carry live-style noise."""
    try:
        if name == "terminal":
            cmd = args.get("command", "")
            r = subprocess.run(cmd, shell=True, cwd=SBX, capture_output=True, text=True,
                               timeout=max(5, min(int(args.get("timeout_s", 60)), 120)))
            out = ((r.stdout or "") + (r.stderr or "")).strip() or "(no output)"
            return out[:1500]
        if name == "read_file":
            p = SBX / args.get("path", "")
            data = open(p, encoding=args.get("encoding", "utf-8"),
                        errors="replace").read(int(args.get("max_bytes", 20000)))
            return f"[read_file] {len(data)} bytes\n{data}"
        if name == "write_file":
            p = SBX / args.get("path", "")
            p.parent.mkdir(parents=True, exist_ok=True)
            open(p, "w", encoding="utf-8").write(args.get("content", ""))
            return f"[write_file] wrote {len(args.get('content',''))} bytes to {args.get('path')}"
        if name == "list_dir":
            p = SBX / (args.get("path") or ".")
            ents = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())
            return "[list_dir]\n" + "\n".join(ents)
        if name == "search_files":
            q, cs = args.get("query", ""), bool(args.get("case_sensitive", True))
            hits = []
            for f in SBX.rglob("*.txt"):
                for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    hay = line if cs else line.lower()
                    if (q if cs else q.lower()) in hay:
                        hits.append(f"{f.name}:{i}: {line.strip()[:80]}")
            noise = f"[search_files] scanned {len(list(SBX.rglob('*.txt')))} files"
            return noise + ("\n" + "\n".join(hits[:40]) if hits else "\n(no matches)")
    except Exception as e:
        return f"(tool error {type(e).__name__}: {e})"
    return f"(unknown tool {name})"

def csv_rows(n, seed):
    rng = random.Random(seed)
    rows = ["id,region,units,price"]
    for i in range(n):
        rows.append(f"{i},{rng.choice(['nsw','vic','qld','wa'])},{rng.randint(1,40)},{rng.randint(10,99)}")
    return "\n".join(rows)

def audit_pair(seed):
    """C4: paired vuln/benign look-alike snippets -> (content, is_vuln, expected_verdict)."""
    rng = random.Random(seed)
    pat = rng.choice(["eval", "sql-concat", "hardcoded-secret"])
    if pat == "eval":
        vuln = ("def run_expr(expr):\n    return eval(expr)  # user-supplied\n")
        benign = ("def run_expr(expr):\n    import ast\n    return ast.literal_eval(expr)\n")
    elif pat == "sql-concat":
        vuln = ("def find_user(c, name):\n    return c.execute('SELECT * FROM users "
                "WHERE name=\\'' + name + '\\'').fetchall()\n")
        benign = ("def find_user(c, name):\n    return c.execute('SELECT * FROM users "
                "WHERE name=?', (name,)).fetchall()\n")
    else:
        vuln = ("API_KEY = 'sk-live-9f3kd83jd8'\n\ndef get_key():\n    return API_KEY\n")
        benign = ("import os\n\ndef get_key():\n    return os.environ.get('API_KEY')\n")
    return (vuln, True) if seed % 2 == 0 else (benign, False)

def mk(seed):
    """Returns setup_cmds, task, followup(or None), verify2(or None), fam."""
    rng = random.Random(seed)
    fam = seed % 12
    setup, task, followup, verify2 = [], "", None, None
    reg = rng.choice(["nsw", "vic", "qld"])
    if fam == 0:  # CSV analytics (typed read/write)
        data = csv_rows(rng.randint(8, 14), seed)
        setup = [f'python -c "open(\'sales.csv\',\'w\').write({data!r})"']
        task = (f"In sales.csv: compute TOTAL revenue (units*price over all rows) and the "
                f"number of rows where region={reg}. Write total.txt with ONLY the integer "
                f"total, and count.txt with ONLY the count.")
        def verify():
            try:
                lines = [l for l in open(SBX / "sales.csv").read().splitlines()[1:] if l.strip()]
                tot = sum(int(l.split(",")[2]) * int(l.split(",")[3]) for l in lines)
                cnt = sum(1 for l in lines if l.split(",")[1] == reg)
                return (open(SBX / "total.txt").read().strip() == str(tot)
                        and open(SBX / "count.txt").read().strip() == str(cnt))
            except Exception:
                return False
        followup = "Also write avg.txt with ONLY the average revenue per row, rounded down."
        def verify2():
            try:
                lines = [l for l in open(SBX / "sales.csv").read().splitlines()[1:] if l.strip()]
                tot = sum(int(l.split(",")[2]) * int(l.split(",")[3]) for l in lines)
                return open(SBX / "avg.txt").read().strip() == str(tot // len(lines))
            except Exception:
                return False
    elif fam == 1:  # restructure + manifest
        names = [f"doc{rng.randint(100,999)}.txt" for _ in range(5)]
        setup = [f'echo {n[:-4]} data> {n}' for n in names]
        task = ("Create directory 'archive'. Move every doc*.txt file into it. Then create "
                "archive/manifest.txt listing the moved filenames one per line, sorted.")
        def verify():
            try:
                p = SBX / "archive"
                man = [l.strip() for l in open(p / "manifest.txt").read().splitlines() if l.strip()]
                moved = sorted(x.name for x in p.glob("doc*.txt"))
                return not list(SBX.glob("doc*.txt")) and man == moved and len(moved) == 5
            except Exception:
                return False
        followup = "Now write archive/count.txt with ONLY how many files the manifest lists."
        def verify2():
            try:
                man = [l for l in open(SBX/"archive"/"manifest.txt").read().splitlines() if l.strip()]
                return open(SBX/"archive"/"count.txt").read().strip() == str(len(man))
            except Exception:
                return False
    elif fam == 2:  # merge dedupe sort
        a = "\n".join(sorted({f"key{rng.randint(1,30)}" for _ in range(10)}))
        b = "\n".join(sorted({f"key{rng.randint(1,30)}" for _ in range(10)}))
        setup = [f'python -c "open(\'a.txt\',\'w\').write({a!r})"',
                 f'python -c "open(\'b.txt\',\'w\').write({b!r})"']
        task = ("Merge a.txt and b.txt into merged.txt with all unique lines, sorted, one per "
                "line. Then write n.txt containing ONLY the number of unique lines.")
        def verify():
            try:
                u = sorted({*open(SBX/"a.txt").read().split(), *open(SBX/"b.txt").read().split()})
                return (open(SBX/"merged.txt").read().split() == u
                        and open(SBX/"n.txt").read().strip() == str(len(u)))
            except Exception:
                return False
        followup = "Also write first.txt with ONLY the alphabetically first unique line."
        def verify2():
            try:
                u = sorted({*open(SBX/"a.txt").read().split(), *open(SBX/"b.txt").read().split()})
                return open(SBX/"first.txt").read().strip() == u[0]
            except Exception:
                return False
    elif fam == 3:  # config transform + validation
        port = rng.randint(1000, 9999)
        setup = ['python -c "open(\'app.cfg\',\'w\').write(\'host=localhost\\nport=8080\\ndebug=false\\n\')"']
        task = (f"In app.cfg: change port to {port}, set debug to true, keep host. Then create "
                f"check.txt with ONLY 'OK' if the file has exactly 3 lines and no duplicate keys, else 'BAD'.")
        def verify():
            try:
                d = dict(l.strip().split("=") for l in open(SBX/"app.cfg").read().splitlines() if l.strip())
                return (d.get("port") == str(port) and d.get("debug") == "true"
                        and d.get("host") == "localhost"
                        and open(SBX/"check.txt").read().strip() == "OK")
            except Exception:
                return False
        followup = "Now also set a new key log_level=info in app.cfg (keep 4 lines)."
        def verify2():
            try:
                d = dict(l.strip().split("=") for l in open(SBX/"app.cfg").read().splitlines() if l.strip())
                return d.get("log_level") == "info" and d.get("debug") == "true" and len(d) == 4
            except Exception:
                return False
    elif fam == 4:  # log analysis
        ips = [f"10.0.0.{rng.randint(2,250)}" for _ in range(4)]
        logs = [f"{ips[i % 2 if i < 10 else 3]} POST /login {'200' if i % 4 else '401'}"
                for i in range(20)]
        setup = [f'python -c "open(\'auth.log\',\'w\').write({chr(10).join(logs)!r})"']
        task = ("In auth.log: find the IP with the MOST 401 responses. Write top.txt with ONLY "
                "that IP. Write fails.txt with ONLY that IP's 401 count.")
        def verify():
            try:
                from collections import Counter
                c = Counter(l.split()[0] for l in open(SBX/"auth.log").read().splitlines() if " 401" in l)
                ip, n = c.most_common(1)[0]
                return (open(SBX/"top.txt").read().strip() == ip
                        and open(SBX/"fails.txt").read().strip() == str(n))
            except Exception:
                return False
        followup = "Also write total401.txt with ONLY the total count of 401 lines in the whole log."
        def verify2():
            try:
                n = sum(1 for l in open(SBX/"auth.log").read().splitlines() if " 401" in l)
                return open(SBX/"total401.txt").read().strip() == str(n)
            except Exception:
                return False
    elif fam == 5:  # multi-file aggregation
        for i in range(3):
            vals = [str(rng.randint(1, 100)) for _ in range(rng.randint(4, 9))]
            setup.append(f'python -c "open(\'d{i}.txt\',\'w\').write({repr(chr(10).join(vals))})"')
        task = ("d1.txt, d2.txt, d3.txt each contain numbers one per line. Compute the overall "
                "MAX and MIN across all three. Write max.txt with ONLY the max, min.txt with ONLY the min.")
        def verify():
            try:
                allv = [int(x) for i in range(3) for x in open(SBX/f"d{i}.txt").read().split()]
                return (open(SBX/"max.txt").read().strip() == str(max(allv))
                        and open(SBX/"min.txt").read().strip() == str(min(allv)))
            except Exception:
                return False
        followup = "Now write sum.txt with ONLY the sum of all numbers across the three files."
        def verify2():
            try:
                allv = [int(x) for i in range(3) for x in open(SBX/f"d{i}.txt").read().split()]
                return open(SBX/"sum.txt").read().strip() == str(sum(allv))
            except Exception:
                return False
    elif fam == 6:  # rename pattern + count
        setup = [f'echo x> file_{i}.log' for i in range(rng.randint(5, 9))]
        task = ("Rename all file_*.log files to .bak extension (same base name). Then write "
                "count_bak.txt containing ONLY how many .bak files exist now.")
        def verify():
            try:
                bak = list(SBX.glob("file_*.bak"))
                return (not list(SBX.glob("file_*.log"))
                        and open(SBX/"count_bak.txt").read().strip() == str(len(bak)))
            except Exception:
                return False
        followup = "Now delete the largest-numbered file_*.bak and rewrite count_bak.txt with the new count."
        def verify2():
            try:
                baks = sorted(SBX.glob("file_*.bak"), key=lambda p: int(p.stem.split("_")[1]))
                if not baks: return False
                nums = [int(p.stem.split("_")[1]) for p in baks]
                expected_missing = max(nums)
                if any(int(p.stem.split('_')[1]) == expected_missing for p in baks): return False
                return open(SBX/"count_bak.txt").read().strip() == str(len(baks) - 1)
            except Exception:
                return False
    elif fam == 7:  # word transform
        words = [rng.choice(["alpha","beta","gamma","delta","eps","zeta","eta"]) for _ in range(12)]
        setup = [f'python -c "open(\'words.txt\',\'w\').write({repr(chr(10).join(words))})"']
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
        followup = f"Now write uniq.txt with ONLY the count of DIFFERENT words in words.txt."
        def verify2():
            try:
                src = open(SBX/"words.txt").read().splitlines()
                return open(SBX/"uniq.txt").read().strip() == str(len(set(src)))
            except Exception:
                return False
    elif fam in (8, 9):  # C4 audit pairs: 8=vuln, 9=benign look-alike
        content, is_vuln = audit_pair(seed)
        setup = [f'python -c "open(\'code_under_audit.txt\',\'w\').write({content!r})"']
        verdict = "VULNERABLE" if is_vuln else "CLEAN"
        task = ("Audit code_under_audit.txt for security issues. If it contains an unsafe "
                "pattern (eval of user input, SQL string concatenation, or a hardcoded "
                "secret), reply with a single line FINAL: VULNERABLE <one-phrase-why>. "
                "If the code is safe despite looking similar, reply with a single line "
                "FINAL: CLEAN <one-phrase-why>. Do not report style issues as vulnerabilities.")
        def verify():
            try:
                return verdict in open(SBX / "audit_verdict.txt").read()
            except Exception:
                return False
        task += (" Write your verdict line also to audit_verdict.txt "
                 "(only the FINAL line).")
    elif fam == 10:  # messy-schema config wrangle (JSON with missing keys/defaults)
        cfg = json.dumps({"service": {"name": "billing", "retries": 3},
                          "db": {"host": "localhost"}})
        setup = [f'python -c "open(\'settings.json\',\'w\').write({cfg!r})"']
        task = ("settings.json may have missing keys (defaults: port=5432, retries=5, "
                "db.pool=10). Write resolved.json containing the FULL config: every "
                "missing key filled with its default, existing values kept. Keep the "
                "same JSON structure with a top-level 'service' and 'db'.")
        def verify():
            try:
                d = json.load(open(SBX / "resolved.json"))
                svc, db = d.get("service", {}), d.get("db", {})
                return (svc.get("name") == "billing" and svc.get("retries") == 3
                        and svc.get("port", 5432) == 5432 and db.get("host") == "localhost"
                        and db.get("pool") == 10)
            except Exception:
                return False
        followup = "Now write port.txt with ONLY the final resolved service port value."
        def verify2():
            try:
                d = json.load(open(SBX / "resolved.json"))
                return open(SBX / "port.txt").read().strip() == str(d.get("service", {}).get("port", 5432))
            except Exception:
                return False
    else:  # 11: revision follow-up (MT-native)
        data = csv_rows(rng.randint(8, 12), seed)
        setup = [f'python -c "open(\'inventory.csv\',\'w\').write({data!r})"']
        task = ("In inventory.csv: write rows.txt with ONLY the count of data rows "
                "(excluding the header).")
        def verify():
            try:
                lines = [l for l in open(SBX/"inventory.csv").read().splitlines()[1:] if l.strip()]
                return open(SBX/"rows.txt").read().strip() == str(len(lines))
            except Exception:
                return False
        followup = "Actually, also exclude rows where region is wa. Overwrite rows.txt with ONLY that new count."
        def verify2():
            try:
                lines = [l for l in open(SBX/"inventory.csv").read().splitlines()[1:] if l.strip()]
                n = sum(1 for l in lines if l.split(",")[1] != "wa")
                return open(SBX/"rows.txt").read().strip() == str(n)
            except Exception:
                return False
    return setup, task, (followup if (seed % 2 == 0 or fam == 11) and fam not in (8, 9) else None), \
           (verify2 if followup else None), fam, verify

def solve(task, setup, messages=None):
    if messages is None:
        if SBX.exists():
            shutil.rmtree(SBX)
        SBX.mkdir(parents=True)
        for c in setup:
            subprocess.run(c, shell=True, cwd=SBX, capture_output=True, text=True, timeout=60)
        messages = [{"role": "system", "content": SYS},
                    {"role": "user", "content": task}]
    steps = 0
    for _ in range(MAX_TURNS):
        r = requests.post(BASE_URL, json={"messages": messages, "tools": TOOLS,
                                          "temperature": 0.3, "max_tokens": 1200,
                                          "stream": False}, timeout=900)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        messages.append({"role": "assistant", "content": content,
                         "tool_calls": msg.get("tool_calls")})
        calls = msg.get("tool_calls") or []
        if not calls:
            break
        for tc in calls:
            name = tc["function"]["name"]
            if name not in TOOL_NAMES:
                out = f"(unknown tool {name})"
            else:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"command": args} if name == "terminal" else {}
                out = run_tool(name, args)
            messages.append({"role": "tool", "tool_call_id": tc.get("id", "call0"),
                             "content": out})
            steps += 1
    return messages, steps

def format_clean(messages):
    """C5: no code fences / thought leakage in assistant content."""
    for m in messages:
        if m.get("role") == "assistant":
            c = m.get("content") or ""
            if FENCE_RE.search(c) or THINK_RE.search(c):
                return False
    return True

def main():
    banked = rejects = 0
    seed = 0
    t0 = time.time()
    def p(s):
        print(s, flush=True)
    if OUT.exists():
        banked = sum(1 for _ in open(OUT, encoding="utf-8"))
        p(f"[c2] resume: {banked} rows already banked")
    while banked < TARGET and seed < TARGET * 5:
        setup, task, followup, verify2, fam, verify = mk(seed)
        seed += 1
        try:
            messages, steps = solve(task, setup)
            row_ok = steps >= 2 and verify() if fam not in (8, 9) else steps >= 1 and verify()
            if row_ok and followup:
                messages.append({"role": "user", "content": followup})
                messages, steps2 = solve(None, None, messages)
                row_ok = row_ok and steps2 >= 1 and (verify2() if verify2 else False)
                steps += steps2
        except Exception as e:
            p(f"[c2] seed {seed}: error {type(e).__name__} {str(e)[:200]}")
            continue
        phases = 1 if not followup else 2
        if row_ok and format_clean(messages):
            row = {"id": banked, "fam": fam, "phases": phases, "n_steps": steps,
                   "messages": messages, "seed": seed - 1}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            banked += 1
            p(f"[c2] seed {seed}: BANK fam={fam} phases={phases} steps={steps} banked={banked} "
              f"({(time.time()-t0)/60:.1f}m)")
        else:
            rejects += 1
            with open(REJECT_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"seed": seed - 1, "fam": fam, "steps": steps,
                                    "clean": format_clean(messages),
                                    "last": (messages[-1].get("content") or "")[:200]}) + "\n")
            p(f"[c2] seed {seed}: reject fam={fam} steps={steps} rejects={rejects}")
        if banked and banked % 20 == 0:
            p(f"[c2] bank rate {banked}/{banked+rejects} = {banked/(banked+rejects)*100:.0f}%")
    p(f"finish: banked={banked}/{TARGET} rejects={rejects} ({(time.time()-t0)/60:.0f}m)")

if __name__ == "__main__":
    main()