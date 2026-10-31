# Nyx-Audit battery v1 — difficulty-graded smart-contract AUDIT tasks (defensive).
# Mission context: ~/synapsek-internal/research/HANDOFF_audit_security_bot.md,
# knowledge base: ~/synapsek-internal/research/NYX_AUDIT_KNOWLEDGE_BASE.md.
# 12 vulnerable + 2 benign-negative tasks = 14. Machine-checkable ground truth.
#
# PRE-REGISTERED (locked in this commit BEFORE any base/trained results exist):
#   BASE battery acceptance: base model lands 0.40-0.70 on audit_v1 (difficulty law).
#   TRAINED-MODEL GATE (nyx-audit joint-v1): audit_v1 >= 0.75 overall,
#     benign_neg >= 0.80, and joint retrain must not drop
#     sec_v2.1 < 0.683 or office < 0.50 (nyx-2 bars unchanged).
#   Benign precision is the headline metric (GPT-4 tools measured 4.15% on
#   real DeFi contracts; a crying-wolf tool is dead on arrival).
#
# Run against :8001 (spark server, base = Spark-X2.6-1.7B):
#   .venv\Scripts\python.exe scripts\audit_eval_v1.py <label>
import json, re, sys, time
from pathlib import Path
import requests

BASE_URL = "http://127.0.0.1:8001/v1/chat/completions"
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "model"
BENIGN = ("benign_withdraw", "benign_treasury")


def norm(s):
    return re.sub(r"\s+", " ", s.lower().strip())


def yes_no(s, want):
    """First meaningful token decides (yes/no answers drift verbose)."""
    m = re.match(r"\s*(yes|no)\b", s.strip(), re.I)
    return bool(m) and m.group(1).lower() == want


TASKS = [
    # 1. reentrancy — external call before state update
    ("reentrancy_eth",
     "Defensive audit of this Solidity:\n"
     "```solidity\n"
     "contract Vault {\n"
     "    mapping(address => uint256) public balances;\n"
     "    function withdraw(uint256 amount) external {\n"
     "        require(balances[msg.sender] >= amount, 'insufficient');\n"
     "        (bool ok, ) = msg.sender.call{value: amount}('');\n"
     "        balances[msg.sender] -= amount;\n"
     "    }\n"
     "}\n"
     "```\n"
     "Which vulnerability class is this? Answer EXACTLY one line:\n"
     "vuln=<one or two words>; func=<function name>; fix=<one short phrase "
     "(what must happen before the external call)>.\"",
     lambda a: ("reentran" in norm(a)) and ("withdraw" in norm(a)) and
               ("state" in norm(a) or "balance" in norm(a) or "effect" in norm(a)
                or "before" in norm(a) or "update" in norm(a) or "first" in norm(a))),

    # 2. oracle manipulation — spot DEX reserves as price feed
    ("oracle_spot",
     "Defensive audit of this Solidity lending snippet:\n"
     "```solidity\n"
     "contract Lending {\n"
     "    IUniswapV2Pair public pair;   // DAI/WETH pool\n"
     "    function collateralValue(uint256 wethAmount) external view returns (uint256) {\n"
     "        (uint112 reserve0, uint112 reserve1,) = pair.getReserves();\n"
     "        // reserve0 = DAI, reserve1 = WETH\n"
     "        return wethAmount * reserve0 / reserve1;\n"
     "    }\n"
     "}\n"
     "```\n"
     "What is the price source and its key weakness? Answer EXACTLY one line:\n"
     "source=<what the price is computed from>; weakness=<one phrase>; "
     "attack=<one phrase, how an attacker moves the price>.\"",
     lambda a: ("reserve" in norm(a) or "pair" in norm(a) or "dex" in norm(a)
                or "pool" in norm(a) or "amm" in norm(a) or "uniswap" in norm(a)) and
               ("flash" in norm(a) or "manipulat" in norm(a) or "swap" in norm(a))),

    # 3. access control — one unguarded privileged function among guarded ones
    ("access_control",
     "Defensive audit. Four functions in a treasury contract:\n"
     "```solidity\n"
     "function withdraw(uint256 amount) external onlyOwner { ... }\n"
     "function pause() external onlyOwner { ... }\n"
     "function setOwner(address newOwner) external { owner = newOwner; }\n"
     "function deposit() external payable { ... }\n"
     "```\n"
     "Exactly ONE function is missing its access-control check and lets anyone "
     "take over. Answer with ONLY the function name.",
     lambda a: "setowner" in norm(a) and "deposit" not in norm(a.replace("set", ""))),

    # 4. integer overflow — pre-0.8 unchecked arithmetic
    ("overflow_pre08",
     "Defensive audit of this Solidity:\n"
     "```solidity\n"
     "pragma solidity 0.7.6;\n"
     "contract Ledger {\n"
     "    mapping(address => uint256) public owed;\n"
     "    uint256 public totalPaid;\n"
     "    function record(address to, uint256 amount) external {\n"
     "        owed[to] += amount;\n"
     "        totalPaid += amount;\n"
     "    }\n"
     "}\n"
     "```\n"
     "Does THIS compiler version automatically check arithmetic overflow? "
     "Answer EXACTLY one line:\n"
     "class=<vulnerability class if amount is huge, one or two words>; "
     "auto_checked=<yes or no>; result=<one or two words, what the uint256 does>.\"",
     lambda a: ("overflow" in norm(a) or "wrap" in norm(a) or "underflow" in norm(a)) and
               ("no" in norm(a).split() or "unchecked" in norm(a) or " 0.7" in norm(a))),

    # 5. delegatecall risk — user-set implementation
    ("delegatecall_risk",
     "Defensive audit of this wallet contract:\n"
     "```solidity\n"
     "contract SimpleWallet {\n"
     "    address public impl;\n"
     "    function setImpl(address i) external { impl = i; }\n"
     "    function execute(bytes calldata data) external {\n"
     "        (bool ok, ) = impl.delegatecall(data);\n"
     "        require(ok);\n"
     "    }\n"
     "}\n"
     "```\n"
     "Answer EXACTLY one line:\n"
     "op=<the dangerous opcode, one word>; control=<who can set the target, "
     "one or two words>; effect=<one short phrase, what delegatecall executes "
     "in>.\"",
     lambda a: ("delegatecall" in norm(a)) and
               ("anyone" in norm(a) or "unauthorized" in norm(a) or "no one" in norm(a)
                or "unauth" in norm(a) or "user" in norm(a) or "attacker" in norm(a)
                or "missing" in norm(a) or "no access" in norm(a))),

    # 6. upgradability — uninitialized implementation
    ("upgrade_uninit",
     "Defensive audit of a UUPS-style proxy setup. The implementation contract:\n"
     "```solidity\n"
     "contract LogicV1 {\n"
     "    uint256 public value;\n"
     "    function initialize() external initializer { value = 1; }\n"
     "    constructor() { }   // empty\n"
     "}\n"
     "```\n"
     "The proxy points at LogicV1. What is missing from the implementation "
     "constructor to stop an attacker calling initialize() DIRECTLY on the "
     "implementation? Answer EXACTLY one line:\n"
     "missing=<one call, function name in snake case>; "
     "risk=<one phrase, what the attacker gains>.\"",
     lambda a: ("disableinitializers" in norm(a) or "disable_initializers" in norm(a)
                or "initializer" in norm(a))),

    # 7. BENIGN NEGATIVE — correct CEI + guard (must say NO)
    ("benign_withdraw",
     "Defensive audit of this Solidity:\n"
     "```solidity\n"
     "contract Vault {\n"
     "    mapping(address => uint256) public balances;\n"
     "    bool private locked;\n"
     "    modifier noReentry() { require(!locked, 'reentrant'); locked = true; _; locked = false; }\n"
     "    function withdraw(uint256 amount) external noReentry {\n"
     "        require(balances[msg.sender] >= amount, 'insufficient');\n"
     "        balances[msg.sender] -= amount;\n"
     "        (bool ok, ) = msg.sender.call{value: amount}('');\n"
     "        require(ok, 'transfer failed');\n"
     "    }\n"
     "}\n"
     "```\n"
     "Is there a reentrancy vulnerability in this contract? Answer YES or NO "
     "first, then one short reason.",
     lambda a: yes_no(a, "no")),

    # 8. BENIGN NEGATIVE — correct two-step ownership (must say NO)
    ("benign_treasury",
     "Defensive audit of this Solidity:\n"
     "```solidity\n"
     "contract Treasury {\n"
     "    address public owner;\n"
     "    address public pendingOwner;\n"
     "    modifier onlyOwner() { require(msg.sender == owner, 'not owner'); _; }\n"
     "    function setPendingOwner(address p) external onlyOwner { pendingOwner = p; }\n"
     "    function acceptOwnership() external {\n"
     "        require(msg.sender == pendingOwner, 'not pending');\n"
     "        owner = pendingOwner; pendingOwner = address(0);\n"
     "    }\n"
     "}\n"
     "```\n"
     "Is there an access-control vulnerability in this contract (a privileged "
     "function without auth, or a takeover path)? Answer YES or NO first, "
     "then one short reason.",
     lambda a: yes_no(a, "no")),

    # 9. ERC-4626-style first-depositor / donation inflation
    ("vault_inflation",
     "Defensive audit of this vault:\n"
     "```solidity\n"
     "contract MiniVault {\n"
     "    uint256 public totalShares;\n"
     "    uint256 public totalAssets;\n"
     "    function deposit(uint256 assets) external returns (uint256 shares) {\n"
     "        shares = totalShares == 0 ? assets : assets * totalShares / totalAssets;\n"
     "        totalShares += shares;\n"
     "        totalAssets += assets;\n"
     "    }\n"
     "}\n"
     "```\n"
     "Rounding/first-depositor risk: if totalAssets is 0 and an attacker "
     "deposits 1 wei first (or donates to inflate), who benefits from the "
     "rounding? Answer EXACTLY one line:\n"
     "class=<one or two words>; first_beneficiary=<who profits, one or two words>; "
     "fix=<one phrase>.\"",
     lambda a: ("rounding" in norm(a) or "inflation" in norm(a) or "donation" in norm(a)
                or "first" in norm(a) or "share" in norm(a)) and
               ("first" in norm(a) or "attacker" in norm(a) or "depositor" in norm(a))),

    # 10. rounding direction — fees must round against the user
    ("rounding_fee",
     "A protocol takes a fee of amountIn * 30 / 10000 (30 bps) from the user's "
     "token amount. In exact math the fee often has a fractional part. To "
     "NEVER undercharge the user, which way must the FEE be rounded? "
     "Answer EXACTLY one line:\n"
     "fee=<floor or ceil>; direction=<one phrase, toward or away from the user>; "
     "why=<one short phrase>.\"",
     lambda a: ("ceil" in norm(a).replace(" ", "") or
               "roundup" in norm(a).replace(" ", ""))),

    # 11. tx.origin authentication
    ("tx_origin",
     "Defensive audit:\n"
     "```solidity\n"
     "contract Payment {\n"
     "    address public owner = tx.origin;\n"
     "    function payOut(uint256 amount) external {\n"
     "        require(tx.origin == owner, 'not owner');\n"
     "        payable(msg.sender).transfer(amount);\n"
     "    }\n"
     "}\n"
     "```\n"
     "What authentication value is misused, and what should replace it? "
     "Answer EXACTLY one line:\n"
     "misused=<one expression>; correct=<one expression>; "
     "risk=<one phrase, the attack class that abuses it>.\"",
     lambda a: ("tx.origin" in norm(a) or "origin" in norm(a) or "tx origin" in norm(a)) and
               ("msg.sender" in norm(a))),

    # 12. unchecked low-level send
    ("unchecked_send",
     "Defensive audit:\n"
     "```solidity\n"
     "contract Payout {\n"
     "    function payout(address payable to, uint256 amount) external {\n"
     "        bool ok = to.send(amount);\n"
     "    }\n"
     "}\n"
     "```\n"
     "send() can fail silently. What does the code fail to do? "
     "Answer EXACTLY one line:\n"
     "missing=<one short phrase>; result=<one short phrase, what breaks>.\"",
     lambda a: ("return" in norm(a) or "result" in norm(a) or "ok" in norm(a)) and
               ("check" in norm(a) or "require" in norm(a) or "revert" in norm(a)
                or "ignore" in norm(a) or "ignored" in norm(a) or "handle" in norm(a))),

    # 13. signature replay — missing nonce + domain separator
    ("sig_replay",
     "Defensive audit of a meta-transaction contract:\n"
     "```solidity\n"
     "contract MetaPay {\n"
     "    function transferWithSig(\n"
     "        address from, address to, uint256 amount,\n"
     "        uint8 v, bytes32 r, bytes32 s\n"
     "    ) external {\n"
     "        bytes32 hash = keccak256(abi.encodePacked(from, to, amount));\n"
     "        address signer = ecrecover(hash, v, r, s);\n"
     "        require(signer == from, 'bad sig');\n"
     "        // ... transfer amount from => to\n"
     "    }\n"
     "}\n"
     "```\n"
     "The SAME signature can be replayed forever (and on other chains). "
     "TWO protections are missing from the signed message. Answer EXACTLY "
     "one line:\n"
     "missing1=<one word>; missing2=<one word or short phrase (chain binding)>.\"",
     lambda a: ("nonce" in norm(a)) and
               ("domain" in norm(a) or "chainid" in norm(a) or "chain" in norm(a)
                or "chain id" in norm(a) or "712" in norm(a))),

    # 14. on-chain randomness
    ("blockhash_random",
     "Defensive audit of a lottery:\n"
     "```solidity\n"
     "contract Lottery {\n"
     "    address[] public players;\n"
     "    address public winner;\n"
     "    function pickWinner() external {\n"
     "        uint256 seed = uint256(blockhash(block.number - 1));\n"
     "        winner = players[seed % players.length];\n"
     "    }\n"
     "}\n"
     "```\n"
     "Can a validator or builder predict or bias this seed? Answer EXACTLY "
     "one line:\n"
     "predictable=<yes or no>; source=<one or two words, what the seed comes "
     "from>; replacement=<one or two words, the standard safe source>.\"",
     lambda a: (("yes" in norm(a).split()[:3] or "yes" in norm(a)) and
               ("block" in norm(a) or "chain" in norm(a)) and
               ("vrf" in norm(a) or "commit" in norm(a) or "reveal" in norm(a)
                or "oracle" in norm(a) or "off-chain" in norm(a) or "off chain" in norm(a)))),
]


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
            ok = bool(check(ans or ""))
        except Exception as e:
            ans, ok = f"ERROR {type(e).__name__}", False
        secs = round(time.time() - t0, 1)
        results[name] = {"pass": ok, "answer": (ans or "")[:200], "secs": secs}
        print(f"[audit1:{name}] {'PASS' if ok else 'FAIL'}: "
              f"{(ans or '')[:100]!r} ({secs}s)", flush=True)

    n = len(results)
    acc = sum(v["pass"] for v in results.values()) / n
    benign_neg = [results[k] for k in BENIGN]
    benign_acc = sum(v["pass"] for v in benign_neg) / len(benign_neg)
    vuln = [v for k, v in results.items() if k not in BENIGN]
    vuln_recall = sum(v["pass"] for v in vuln) / len(vuln)
    # false positive on benign = model claims a vulnerability that is not there
    fp_rate = sum(1 for v in benign_neg if not v["pass"]) / len(benign_neg)
    summary = {
        "model": LABEL, "audit_v1_acc": acc, "n": n,
        "benign_neg_acc": benign_acc, "benign_fp_rate": fp_rate,
        "vuln_recall": vuln_recall,
        "verdict": ("IN BAND (0.40-0.70) -> collect+train"
                    if 0.40 <= acc <= 0.70 else
                    ("TOO HARD (<0.40) -> simplify" if acc < 0.40
                     else "TOO EASY (>0.70) -> harden")),
        "detail": results,
    }
    (OUT / f"audit_eval_v1_{LABEL}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in
                      ("model", "audit_v1_acc", "n", "benign_neg_acc",
                       "benign_fp_rate", "vuln_recall", "verdict")},
                     indent=2), flush=True)


if __name__ == "__main__":
    main()