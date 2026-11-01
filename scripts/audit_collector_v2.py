# Nyx-2 Audit collector v2 — BREADTH archetypes (under-detected 2023-26 classes
# from NYX_AUDIT_KNOWLEDGE_BASE.md). 8 NEW classes, none in the v1 space:
#   k1 read-only reentrancy (view fn reentering state)
#   k2 ERC-4626 donation/inflation (direct-transfer inflation, not just first-depositor)
#   k3 ERC-7702 delegation risk (authorized delegate takeover)
#   k4 compositional approve/transferFrom (missing allowance reset / infinite approval)
#   k5 gas griefing (unbounded loop / pull-payments denial)
#   k6 oracle TWAP window too short (manipulation window)
#   k7 uninitialized-implementation variant (Vyper-style / initializer re-run)
#   k8 fee-on-transfer accounting (token balance mismatch)
# ALL DEFENSIVE. Machine-verified against programmatic ground truth -> work_audit2.jsonl.
# PRE-REGISTERED BARS (frozen BEFORE any v2 data is collected):
#   audit_v2 battery (fresh instances of these 8): >= 0.70 trained,
#   audit_v1 battery >= 0.90 held, benign >= 0.80 held, sec/office bars held.
# Run with teacher on :8002 (collector auto-connects):
#   .venv\Scripts\python.exe scripts\audit_collector_v2.py
import json, os, random, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
OUT = Path(os.environ.get("NYX_OUT",
    r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1"))
WORK = OUT / "work_audit2.jsonl"
LOG = OUT / "audit2_collect_log.txt"
TARGET = 800
N_TASKS = 1400

SYS = ("You are a precise smart-contract security auditor. Answer EVERY task "
       "with ONLY the exact answer line requested - no preamble, no plan. "
       "Many contracts are SAFE: answer YES only with a concrete attack "
       "path through the actual code, otherwise answer NO.")

def log(m):
    line = f"[audit2] {time.strftime('%H:%M:%S')} {m}"
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")

def gen_tasks():
    tasks = {}
    for i in range(N_TASKS):
        rng = random.Random(17000 + i)
        k = 1 + (i % 8)
        if k == 1:  # read-only reentrancy
            fn = rng.choice(["getShares", "previewRedeem", "quote", "valueOf"])
            tok = rng.choice(["balances", "shares", "deposits"])
            prompt = (f"Defensive audit:\n```solidity\n"
                      f"contract Pool {{\n"
                      f"    mapping(address => uint256) public {tok};\n"
                      f"    function {fn}(address u) external view returns (uint256) {{\n"
                      f"        uint256 v = {tok}[u] * rate();\n"
                      f"        // rate() is an EXTERNAL call (to another contract)\n"
                      f"        // and state is WRITTEN in a callback path reachable\n"
                      f"        // during rate(); view here, but writes happen mid-read\n"
                      f"        return v;\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"Can this view function enable a read-only reentrancy "
                      f"attack (state skewed while being read by another "
                      f"protocol)? Answer EXACTLY one line: vuln=<class, one "
                      f"or two words>; condition=<one phrase>; fix=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return "reentran" in al and ("read" in al or "view" in al)
            tasks[i] = (prompt, chk)
        elif k == 2:  # 4626 donation inflation
            dep = rng.choice(["deposit", "mint"])
            prompt = (f"Defensive audit of an ERC-4626 vault:\n```solidity\n"
                      f"contract Vault {{\n"
                      f"    IERC20 public asset;\n"
                      f"    uint256 public totalShares, totalAssets;\n"
                      f"    function {dep}(uint256 amt) external returns (uint256 s) {{\n"
                      f"        s = convertToShares(amt);\n"
                      f"        totalShares += s; totalAssets += amt;\n"
                      f"    }}\n"
                      f"    function convertToShares(uint256 a) public view returns (uint256) {{\n"
                      f"        uint256 bal = asset.balanceOf(address(this));\n"
                      f"        return bal == 0 ? a : a * totalShares / bal;\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"A attacker can TRANSFER tokens directly to the vault "
                      f"(not via {dep}) before a victim {dep}. What does this "
                      f"donation do to the victim's shares? Answer EXACTLY one "
                      f"line: vuln=<class>; effect=<one phrase>; fix=<one "
                      f"phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("inflat" in al or "donat" in al or "donation" in al
                        or "skew" in al or "dilut" in al) and (
                    "share" in al or "victim" in al or "round" in al or
                    "less" in al or "dilut" in al)
            tasks[i] = (prompt, chk)
        elif k == 3:  # ERC-7702 delegation
            prompt = (f"Defensive audit (ERC-7702 era, 2025+). An EOA signs an "
                      f"authorization making a CONTRACT its delegate:\n"
                      f"```solidity\n"
                      f"contract DelegateImpl {{\n"
                      f"    function drain(address to) external onlySelf {{\n"
                      f"        // requires the delegate's own logic to authorize\n"
                      f"        // but the EOA's nonce replay was not checked\n"
                      f"        payable(to).transfer(address(this).balance);\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"What protection must the authorization include "
                      f"(the one replay-related protection)? Answer EXACTLY "
                      f"one line: missing=<one or two words>; risk=<one "
                      f"phrase>.\"")
            def chk(a):
                al = a.lower()
                return "nonce" in al and ("replay" in al or "re-use" in al
                        or "reuse" in al or "valid" in al or "expir" in al)
            tasks[i] = (prompt, chk)
        elif k == 4:  # allowance reset / infinite approval
            fn = rng.choice(["approve", "permit"])
            prompt = (f"Defensive audit:\n```solidity\n"
                      f"contract TokenCompat {{\n"
                      f"    mapping(address => mapping(address => uint256)) public allowance;\n"
                      f"    function {fn}(address spender, uint256 amt) external returns (bool) {{\n"
                      f"        allowance[msg.sender][spender] = amt;   // no diff check\n"
                      f"        return true;\n"
                      f"    }}\n"
                      f"    function transferFrom(address f, address t, uint256 a) external returns (bool) {{\n"
                      f"        uint256 al = allowance[f][msg.sender];\n"
                      f"        if (al != type(uint256).max) {{ allowance[f][msg.sender] = al - a; }}\n"
                      f"        _transfer(f, t, a);\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"Two questions: (1) does {fn} need a reset-to-zero step "
                      f"first (front-running race), (2) what does the max-allowance "
                      f"bypass in transferFrom enable? Answer EXACTLY one line: "
                      f"race=<yes/no>; infinite=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("yes" in al[:40]) and ("infinite" in al or "never decremented" in al
                        or "not decremented" in al or "unlimited" in al or "max" in al)
            tasks[i] = (prompt, chk)
        elif k == 5:  # gas griefing unbounded loop
            prompt = (f"Defensive audit:\n```solidity\n"
                      f"contract BatchPay {{\n"
                      f"    function payAll(address[] calldata to, uint256 amt) external {{\n"
                      f"        for (uint256 i = 0; i < to.length; i++) {{\n"
                      f"            (bool ok, ) = to[i].call{{value: amt}}('');\n"
                      f"            require(ok);\n"
                      f"        }}\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"An attacker controls part of the list. What are the "
                      f"TWO denial vectors? Answer EXACTLY one line: "
                      f"v1=<one phrase>; v2=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("gas" in al or "out of gas" in al or "grief" in al or "dos" in al
                        or "revert" in al or "unbounded" in al) and (
                    "revert" in al or "fail" in al or "gas" in al or "call" in al
                    or "loop" in al)
            tasks[i] = (prompt, chk)
        elif k == 6:  # oracle TWAP too short
            w = rng.choice([1, 2, 3])
            prompt = (f"Defensive audit of a lending liquidation path:\n"
                      f"```solidity\n"
                      f"contract Oracle {{\n"
                      f"    IUniswapV3Pool public pool;\n"
                      f"    function price() external view returns (uint256) {{\n"
                      f"        (int24 twTick,) = pool.observe({w});   // {w}-second TWAP\n"
                      f"        return TickMath.getSqrtRatioAtTick(twTick);\n"
                      f"    }}\n"
                      f"}}\n"
                      f"// liquidation uses price() in the SAME block as a\n"
                      f"// pool-manipulating flash loan\n"
                      f"```\n"
                      f"Why is a {w}-second TWAP unsafe for instant "
                      f"liquidation? Answer EXACTLY one line: "
                      f"reason=<one line>; fix=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("window" in al or "short" in al or "small" in al or
                        "manipul" in al or "flash" in al or "one block" in al or
                        "within" in al) and (
                    "longer" in al or "window" in al or "median" in al or
                    "increase" in al or "twap" in al or "minutes" in al or
                    "aggregate" in al)
            tasks[i] = (prompt, chk)
        elif k == 7:  # initializer re-run variant
            prompt = (f"Defensive audit (proxy + implementation pattern):\n"
                      f"```solidity\n"
                      f"contract ImplV1 {{\n"
                      f"    bool private initialized;\n"
                      f"    function initialize(address newOwner) external {{\n"
                      f"        // missing initialized check\n"
                      f"        owner = newOwner;\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"Anyone can call initialize() on the IMPLEMENTATION "
                      f"and later via the proxy? What EXACTLY is missing? "
                      f"Answer EXACTLY one line: missing=<one short phrase>; "
                      f"impact=<one phrase>.\"")
            def chk(a):
                al = a.lower().replace(" ", "").replace("_", "")
                return ("initialized" in al or "initializer" in al or
                        "once" in al) and (
                    "owner" in al or "takeover" in al or "again" in al or
                    "re-initial" in al or "reinit" in al)
            tasks[i] = (prompt, chk)
        else:  # k8 fee-on-transfer
            prompt = (f"Defensive audit of a swap/pool that receives "
                      f"fee-on-transfer tokens:\n```solidity\n"
                      f"contract Router {{\n"
                      f"    function swapExactIn(uint256 amtIn) external {{\n"
                      f"        IERC20(t).transferFrom(msg.sender, address(this), amtIn);\n"
                      f"        uint256 got = amtIn;   // assumes no fee\n"
                      f"        pool.swap(got);\n"
                      f"    }}\n"
                      f"}}\n```\n"
                      f"If the token takes a transfer fee, what breaks and "
                      f"what is the fix? Answer EXACTLY one line: "
                      f"breaks=<one phrase>; fix=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("balance" in al or "amount" in al or "under" in al or
                        "less" in al or "actual" in al or "deficit" in al) and (
                    "balanceof" in al or "after" in al or "actual" in al or
                    "measure" in al or "received" in al)
            tasks[i] = (prompt, chk)
    return tasks

def answer(prompt):
    r = requests.post(BASE_URL, json={
        "messages": [{"role": "system", "content": SYS},
                      {"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 700, "stream": False}, timeout=900)
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
            ans = answer(prompt)
            ok = bool(chk(ans))
        except Exception as e:
            log(f"task {i}: ERROR {type(e).__name__}"); continue
        dt = time.time() - t0
        log(f"task {i} (k {1+i%8}): {'BANK' if ok else 'reject'} ({dt:.0f}s) banked={banked+1 if ok else banked}")
        if ok:
            banked += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "kind": 1+i%8, "secs": round(dt),
                        "messages": [{"role": "user", "content": prompt},
                                     {"role": "assistant", "content": ans}]}) + "\n")
    log(f"finish: banked={banked}/{TARGET}")

if __name__ == "__main__":
    main()