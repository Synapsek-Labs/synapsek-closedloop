# Nyx-2 Audit collector v1 — 14 defensive smart-contract audit archetypes.
# Mirrors audit_eval_v1.py battery v1.1 (same archetype space, PARAMETERIZED
# instances so the battery at gate time uses fresh unseen contracts).
# ALL DEFENSIVE: identify weaknesses in code WE generated for training;
# no exploit payloads, no live targets. Answers machine-verified against
# programmatically known ground truth before banking -> work_audit.jsonl.
# Target 400 rows (audit = vertical #3; joint retrain consumes it with the
# other 4 banks per the interference law - never audit-only).
# Run with teacher up on :8002:
#   .venv\Scripts\python.exe scripts\audit_collector_v1.py
import json, os, random, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8002/v1/chat/completions"
OUT = Path(os.environ.get(
    "NYX_OUT",
    r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1",
))
WORK = OUT / "work_audit.jsonl"
LOG = OUT / "audit1_collect_log.txt"
TARGET = 550          # v1.1: 400 existing + ~150 top-up (benign quota below)
N_TASKS = 1400
BENIGN_KINDS = (7, 8)
BENIGN_TARGET = 80

PREFIX = "Defensive audit of this Solidity (blue-team: identify and fix):\n"

# Same SYS framing as audit_eval_v1.py battery + the safety clause that stops
# the teacher from fabricating vulnerabilities on benign contracts.
SYS = ("You are a precise smart-contract security auditor. Answer EVERY task "
       "with ONLY the exact answer line requested - no preamble, no plan, no "
       "restating the task. Copy the format exactly. Many contracts you review "
       "are SAFE: answer YES only when you can trace a complete concrete "
       "attack path through the actual code, otherwise answer NO.")


def log(msg):
    line = f"[audit1] {time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def gen_tasks():
    tasks = {}
    for i in range(N_TASKS):
        rng = random.Random(9000 + i)
        k = 1 + (i % 14)
        # --- k1 reentrancy (CEI violation) ---
        if k == 1:
            c = rng.choice(["Vault", "Bank", "Escrow", "PrizePool"])
            fn = rng.choice(["withdraw", "claim", "cashOut", "takeOut"])
            tok = rng.choice(["balances", "shares", "credits"])
            req = rng.choice(["insufficient", "no funds", "bad amount"])
            prompt = (f"{PREFIX}```solidity\ncontract {c} {{\n"
                      f"    mapping(address => uint256) public {tok};\n"
                      f"    function {fn}(uint256 amount) external {{\n"
                      f"        require({tok}[msg.sender] >= amount, '{req}');\n"
                      f"        (bool ok, ) = msg.sender.call{{value: amount}}('');\n"
                      f"        {tok}[msg.sender] -= amount;\n"
                      f"    }}\n}}\n```\n"
                      f"Which vulnerability class is this, which function, "
                      f"and what is the fix? Answer EXACTLY one line:\n"
                      f"vuln=<one or two words>; func=<function name>; "
                      f"fix=<one short phrase>.\"")
            def chk(a, fn=fn):
                al = a.lower().replace(" ", "")
                return ("reent" in al or "reentr" in al) and fn.lower() in al
            tasks[i] = (prompt, chk)
        # --- k2 oracle manipulation (spot reserves) ---
        elif k == 2:
            pool = rng.choice(["pair", "pool", "dexPair"])
            a0 = rng.choice(["DAI", "USDC", "TUSD"])
            a1 = rng.choice(["WETH", "WBTC", "WSTETH"])
            prompt = (f"{PREFIX}```solidity\ncontract Lending {{\n"
                      f"    IUniswapV2Pair public {pool};   // {a0}/{a1}\n"
                      f"    function collateralValue(uint256 amt) external view "
                      f"returns (uint256) {{\n"
                      f"        (uint112 r0, uint112 r1,) = {pool}.getReserves();\n"
                      f"        return amt * r0 / r1;\n"
                      f"    }}\n}}\n```\n"
                      f"What is the price source, its key weakness, and how "
                      f"does an attacker move the price? Answer EXACTLY one "
                      f"line: source=<what the price is computed from>; "
                      f"weakness=<one phrase>; attack=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return (("reserve" in al or "pair" in al or "pool" in al
                         or "dex" in al or "amm" in al or "uniswap" in al)
                        and ("flash" in al or "manipul" in al or "swap" in al))
            tasks[i] = (prompt, chk)
        # --- k3 access control (one unguarded fn) ---
        elif k == 3:
            bad = rng.choice(["setOwner", "setAdmin", "setFeeTo",
                              "setTreasury", "setGovernor"])
            good = rng.choice([("withdraw", "pause"), ("deposit", "sweep"),
                               ("claim", "stop")])
            prompt = (f"{PREFIX}```solidity\ncontract Treasury {{\n"
                      f"    function {good[0]}(uint256 x) external onlyOwner "
                      f"{{ ... }}\n"
                      f"    function {good[1]}() external onlyOwner {{ ... }}\n"
                      f"    function {bad}(address n) external {{ owner = n; }}\n"
                      f"    function deposit() external payable {{ ... }}\n"
                      f"}}\n```\n"
                      f"Exactly ONE function is missing its access-control "
                      f"check and lets anyone take over. Answer with ONLY "
                      f"the function name.\"")
            def chk(a, bad=bad):
                al = a.lower().replace(" ", "").replace("`", "")
                return bad.lower() in al
            tasks[i] = (prompt, chk)
        # --- k4 integer overflow pre-0.8 ---
        elif k == 4:
            minor = rng.choice(["6", "5", "7"])
            c = rng.choice(["Ledger", "Book", "Accounting"])
            m = rng.choice(["owed", "due", "pending"])
            prompt = (f"{PREFIX}```solidity\npragma solidity 0.7.{minor};\n"
                      f"contract {c} {{\n"
                      f"    mapping(address => uint256) public {m};\n"
                      f"    uint256 public totalPaid;\n"
                      f"    function record(address to, uint256 amount) "
                      f"external {{\n"
                      f"        {m}[to] += amount;\n"
                      f"        totalPaid += amount;\n"
                      f"    }}\n}}\n```\n"
                      f"Does THIS compiler version automatically check "
                      f"arithmetic overflow? Answer EXACTLY one line:\n"
                      f"class=<vulnerability class if amount is huge>; "
                      f"auto_checked=<yes or no>; "
                      f"result=<what the uint256 does>.\"")
            def chk(a):
                al = a.lower()
                return (("overflow" in al or "wrap" in al or "underflow" in al)
                        and ("not automatically" in al or "no automatic" in al
                             or "unchecked" in al or "not checked" in al
                             or "auto_checked=no" in al.replace(" ", "")))
            tasks[i] = (prompt, chk)
        # --- k5 delegatecall to user-set target ---
        elif k == 5:
            c = rng.choice(["SimpleWallet", "Wallet", "Executor"])
            prompt = (f"{PREFIX}```solidity\ncontract {c} {{\n"
                      f"    address public impl;\n"
                      f"    function setImpl(address i) external {{ impl = i; }}\n"
                      f"    function execute(bytes calldata data) external {{\n"
                      f"        (bool ok, ) = impl.delegatecall(data);\n"
                      f"        require(ok);\n"
                      f"    }}\n}}\n```\n"
                      f"Answer EXACTLY one line: op=<the dangerous opcode>; "
                      f"control=<who can set the target>; effect=<what "
                      f"delegatecall executes in>.\"")
            def chk(a):
                al = a.lower()
                return ("delegatecall" in al and (
                    "anyone" in al or "attacker" in al or "user" in al
                    or "no one" in al or "missing" in al or "unprotected" in al
                    or "no restriction" in al or "no access" in al))
            tasks[i] = (prompt, chk)
        # --- k6 uninitialized implementation ---
        elif k == 6:
            prompt = (f"{PREFIX}UUPS-style proxy setup. The implementation:\n"
                      f"```solidity\ncontract LogicV1 {{\n"
                      f"    uint256 public value;\n"
                      f"    function initialize() external initializer "
                      f"{{ value = 1; }}\n"
                      f"    constructor() {{ }}   // empty\n}}\n```\n"
                      f"The proxy points at LogicV1. What call is missing from "
                      f"the implementation constructor so an attacker cannot "
                      f"call initialize() DIRECTLY on the implementation? (Standard "
                      f"OpenZeppelin-style UUPS implementations lock their "
                      f"constructors.) Answer EXACTLY one line: "
                      f"missing=<one call>; risk=<what the attacker gains>.\"")
            def chk(a):
                al = a.lower().replace(" ", "").replace("_", "")
                return ("disableinitializers" in al or "disableinitializer" in al)
            tasks[i] = (prompt, chk)
        # --- k7 BENIGN: correct guarded withdraw ---
        elif k == 7:
            locked = rng.choice(["locked", "noReentry", "guard", "busy"])
            prompt = (f"{PREFIX}```solidity\ncontract Vault {{\n"
                      f"    mapping(address => uint256) public balances;\n"
                      f"    bool private {locked};\n"
                      f"    modifier noReentry() {{ require(!{locked}, 're'); "
                      f"{locked} = true; _; {locked} = false; }}\n"
                      f"    function withdraw(uint256 amount) external "
                      f"noReentry {{\n"
                      f"        require(balances[msg.sender] >= amount, 'x');\n"
                      f"        balances[msg.sender] -= amount;\n"
                      f"        (bool ok, ) = msg.sender.call{{value: amount}}"
                      f"('');\n"
                      f"        require(ok);\n    }}\n}}\n```\n"
                      f"Is there a reentrancy vulnerability here? Answer YES "
                      f"only if you can name a concrete exploitable path; "
                      f"otherwise answer NO. YES or NO first, then one short "
                      f"reason.\"")
            def chk(a):
                import re as _re
                m = _re.match(r"\s*(no)\b", a.strip(), _re.I)
                al = a.lower()
                return bool(m) or ("no vulnerability" in al
                                   or "is safe" in al or "not vulnerable" in al)
            tasks[i] = (prompt, chk)
        # --- k8 BENIGN: correct two-step ownership ---
        elif k == 8:
            prompt = (f"{PREFIX}```solidity\ncontract Treasury {{\n"
                      f"    address public owner;\n"
                      f"    address public pendingOwner;\n"
                      f"    modifier onlyOwner() {{ require(msg.sender == "
                      f"owner); _; }}\n"
                      f"    function setPendingOwner(address p) external "
                      f"onlyOwner {{ pendingOwner = p; }}\n"
                      f"    function acceptOwnership() external {{\n"
                      f"        require(msg.sender == pendingOwner);\n"
                      f"        owner = pendingOwner; pendingOwner = "
                      f"address(0);\n    }}\n}}\n```\n"
                      f"Is there an access-control vulnerability here (a "
                      f"privileged function without auth, or a takeover "
                      f"path)? Answer YES only if you can name a concrete "
                      f"exploitable path; otherwise answer NO. YES or NO "
                      f"first, then one short reason.\"")
            def chk(a):
                import re as _re
                m = _re.match(r"\s*(no)\b", a.strip(), _re.I)
                al = a.lower()
                return bool(m) or ("no vulnerability" in al
                                   or "is safe" in al or "not vulnerable" in al)
            tasks[i] = (prompt, chk)
        # --- k9 vault inflation / rounding ---
        elif k == 9:
            prompt = (f"{PREFIX}```solidity\ncontract MiniVault {{\n"
                      f"    uint256 public totalShares;\n"
                      f"    uint256 public totalAssets;\n"
                      f"    function deposit(uint256 assets) external returns "
                      f"(uint256 shares) {{\n"
                      f"        shares = totalShares == 0 ? assets : "
                      f"assets * totalShares / totalAssets;\n"
                      f"        totalShares += shares;\n"
                      f"        totalAssets += assets;\n    }}\n}}\n```\n"
                      f"Rounding/first-depositor risk: if totalAssets is 0 "
                      f"and an attacker deposits 1 wei first (or donates to "
                      f"inflate), who benefits from the rounding? Answer "
                      f"EXACTLY one line: class=<one or two words>; "
                      f"first_beneficiary=<who profits>; fix=<one phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("rounding" in al or "inflation" in al
                        or "donation" in al or "first" in al or "share" in al) \
                    and ("attacker" in al or "first" in al or "depositor" in al)
            tasks[i] = (prompt, chk)
        # --- k10 fee rounding direction ---
        elif k == 10:
            bps = rng.choice([30, 25, 50, 33])
            prompt = (f"A protocol takes a fee of amountIn * {bps} / 10000 "
                      f"({bps} bps) from the user's token amount. In exact "
                      f"math the fee often has a fractional part. To NEVER "
                      f"undercharge the user, which way must the FEE be "
                      f"rounded? Answer EXACTLY one line: fee=<floor or "
                      f"ceil>; direction=<toward or away from the user>; "
                      f"why=<one short phrase>.\"")
            def chk(a):
                al = a.lower()
                return ("ceil" in al or "round up" in al or "roundup" in al
                        or "up (ceil)" in al or "higher" in al)
            tasks[i] = (prompt, chk)
        # --- k11 tx.origin auth ---
        elif k == 11:
            prompt = (f"{PREFIX}```solidity\ncontract Payment {{\n"
                      f"    address public owner = tx.origin;\n"
                      f"    function payOut(uint256 amount) external {{\n"
                      f"        require(tx.origin == owner, 'not owner');\n"
                      f"        payable(msg.sender).transfer(amount);\n"
                      f"    }}\n}}\n```\n"
                      f"What authentication value is misused, and what should "
                      f"replace it? Answer EXACTLY one line: misused=<one "
                      f"expression>; correct=<one expression>; risk=<the "
                      f"attack class>.\"")
            def chk(a):
                al = a.lower()
                return ("tx.origin" in al or "tx origin" in al
                        or "origin" in al) and (
                    "msg.sender" in al or "msg sender" in al)
            tasks[i] = (prompt, chk)
        # --- k12 unchecked low-level send ---
        elif k == 12:
            prompt = (f"{PREFIX}```solidity\ncontract Payout {{\n"
                      f"    function payout(address payable to, uint256 "
                      f"amount) external {{\n"
                      f"        bool ok = to.send(amount);\n"
                      f"    }}\n}}\n```\n"
                      f"send() can fail silently. What does the code fail to "
                      f"do? Answer EXACTLY one line: missing=<one short "
                      f"phrase>; result=<what breaks>.\"")
            def chk(a):
                al = a.lower()
                return ("return" in al or "result" in al or "ok" in al
                        or "error handling" in al or "error" in al
                        or "silently" in al or "silent" in al) and (
                    "check" in al or "require" in al or "revert" in al
                    or "ignor" in al or "handle" in al or "handling" in al
                    or "verif" in al)
            tasks[i] = (prompt, chk)
        # --- k13 signature replay ---
        elif k == 13:
            prompt = (f"{PREFIX}```solidity\ncontract MetaPay {{\n"
                      f"    function transferWithSig(\n"
                      f"        address from, address to, uint256 amount,\n"
                      f"        uint8 v, bytes32 r, bytes32 s\n"
                      f"    ) external {{\n"
                      f"        bytes32 h = keccak256(abi.encodePacked("
                      f"from, to, amount));\n"
                      f"        address signer = ecrecover(h, v, r, s);\n"
                      f"        require(signer == from, 'bad sig');\n"
                      f"        // ... transfer amount from => to\n"
                      f"    }}\n}}\n```\n"
                      f"The SAME signature can be replayed forever (and on "
                      f"other chains). TWO protections are missing from the "
                      f"signed message. Answer EXACTLY one line: "
                      f"missing1=<one word>; missing2=<one word or short "
                      f"phrase (chain binding)>.\"")
            def chk(a):
                al = a.lower()
                return "nonce" in al and ("chain" in al or "domain" in al
                                          or "712" in al or "separator" in al)
            tasks[i] = (prompt, chk)
        # --- k14 on-chain randomness ---
        else:
            prompt = (f"{PREFIX}```solidity\ncontract Lottery {{\n"
                      f"    address[] public players;\n"
                      f"    address public winner;\n"
                      f"    function pickWinner() external {{\n"
                      f"        uint256 seed = uint256(blockhash("
                      f"block.number - 1));\n"
                      f"        winner = players[seed % players.length];\n"
                      f"    }}\n}}\n```\n"
                      f"Can a validator or builder predict or bias this "
                      f"seed? Answer EXACTLY one line: predictable=<yes or "
                      f"no>; source=<what the seed comes from>; "
                      f"replacement=<the standard safe source>.\"")
            def chk(a):
                al = a.lower()
                return ("yes" in al) and ("block" in al or "chain" in al) and (
                    "vrf" in al or "commit" in al or "reveal" in al
                    or "oracle" in al or "off-chain" in al or "off chain" in al)
            tasks[i] = (prompt, chk)
    return tasks


def answer(prompt):
    r = requests.post(BASE_URL, json={
        "messages": [{"role": "system", "content": SYS},
                      {"role": "user", "content": prompt}],
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
    benign_done = sum(1 for line in
                      (WORK.read_text(encoding="utf-8").splitlines()
                       if WORK.exists() else [])
                      if line.strip()
                      and json.loads(line)["kind"] in BENIGN_KINDS)
    log(f"start: benign banked={benign_done}/{BENIGN_TARGET}")
    for i in sorted(tasks):
        if banked >= TARGET and benign_done >= BENIGN_TARGET:
            log(f"target reached: {banked} (benign {benign_done})"); break
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
        log(f"task {i} (k {1 + i % 14}): {'BANK' if ok else 'reject'} "
            f"({dt:.0f}s) banked={banked + 1 if ok else banked}")
        if ok:
            banked += 1
            if 1 + i % 14 in BENIGN_KINDS:
                benign_done += 1
            with open(WORK, "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": i, "kind": 1 + i % 14,
                                    "secs": round(dt),
                                    "messages": msgs}) + "\n")
    log(f"finish: banked={banked}/{TARGET}")


if __name__ == "__main__":
    main()