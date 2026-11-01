# Nyx-2-joint-v2 GAUNTLET v1 — real-world incident patterns + limit probes.
# NOT a training battery: a capability/limits measurement against documented
# real incidents (defensive identification only). Run against :8001 (live model).
#   .venv\Scripts\python.exe scripts\nyx_gauntlet_v1.py gauntlet-v1
import json, os, sys, time
from pathlib import Path
import requests

BASE_URL = os.environ.get("NYX_BASE_URL", "http://127.0.0.1:8001/v1/chat/completions")
OUT = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "gauntlet"
LOG = OUT / "gauntlet_log.txt"

SYS = ("You are a precise smart-contract security auditor. Answer EVERY task "
       "with ONLY the exact answer line requested - no preamble, no restating. "
       "Many contracts are SAFE: answer YES only with a concrete attack path, "
       "otherwise answer NO.")

def ask(prompt):
    payload = {
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "temperature": 0.2, "max_tokens": 700, "stream": False}
    r = requests.post(BASE_URL, json=payload, timeout=600)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def has(a, *need):
    return all(x in a.lower() for x in need)

TASKS = [
 # --- REAL INCIDENT PATTERNS (ground truth = public post-mortems) ---
 ("real_euler_2023",  # Euler Finance $197M: donateToReserves could push account underwater
  "Post-mortem pattern (Euler-style, 2023). Core logic:\n"
  "```solidity\n"
  "function donateToReserves(uint256 amount) external nonReentrant {\n"
  "    _burn(msg.sender, amount);\n"
  "    reserves += amount;\n"
  "}\n"
  "// _burn reduces user assets but liabilities stay;\n"
  "// health check missing on entry\n"
  "```\n"
  "Name the vulnerability class and missing check. Format: vuln=<class>; missing=<check>.",
  lambda a: (has(a, "donat") or has(a, "health") or has(a, "solvent")
              or has(a, "underwater") or has(a, "liabilit"))),
 ("real_beanstalk_2022",  # Beanstalk $182M: flash-loan governance takeover
  "Post-mortem pattern (Beanstalk-style, 2022). A protocol where arbitrary\n"
  "addresses can submit governance proposals, and proposals EXECUTE in the\n"
  "same transaction that voting completes. Voting power = token balance.\n"
  "```solidity\n"
  "function proposeAndExecute(bytes calldata actions) external {\n"
  "    if (balanceOf(msg.sender) > 51_percent) { executeActions(actions); }\n"
  "}\n"
  "```\n"
  "How is this exploitable in ONE transaction? Format: attack=<one line>; "
  "missing=<protection>.",
  lambda a: has(a, "flash") and (has(a, "gov") or has(a, "vot") or has(a, "proposal"))),
 ("real_wormhole_2022",  # Wormhole $325M: deprecated signature verification (dead code path)
  "Post-mortem pattern (Wormhole-style, 2022). A bridge guardian verification\n"
  "where the OLD verify routine was left callable:\n"
  "```solidity\n"
  "function verifyOld(bytes[] memory sigs, bytes memory data) external {  // deprecated\n"
  "    // trusts guardian set v0 (all-zero for new accounts)\n"
  "    _process(data);\n"
  "}\n"
  "```\n"
  "What class of bug is this? Format: vuln=<class>; fix=<one phrase>.",
  lambda a: has(a, "deprecat") or has(a, "dead") or has(a, "unauthor")
            or has(a, "guardian") or has(a, "signature")),
 ("real_parity_2017",  # Parity multisig: unprotected initWallet via delegatecall
  "Post-mortem pattern (Parity-style, 2017). A library contract\n"
  "delegatecalled by wallets exposes:\n"
  "```solidity\n"
  "function initWallet(address _owner) public {  // no auth, called via delegatecall\n"
  "    owners[_owner] = true;\n"
  "}\n"
  "```\n"
  "What is the bug and impact? Format: vuln=<class>; impact=<one phrase>.",
  lambda a: has(a, "init") or has(a, "unauthor") or has(a, "access") or has(a, "owner")),
 ("real_qubit_2022",  # Qubit $80M: safeTransferFrom ETH vs BEP20 interface mismatch
  "Post-mortem pattern (Qubit-style, 2022). A bridge calls an interface\n"
  "declared as an EVM-ETH token but the underlying chain token (BEP20-like)\n"
  "has no such payable fallback:\n"
  "```solidity\n"
  "interface IDummy { function safeTransferFrom(address,address,uint256) external; }\n"
  "// deposit() assumes tokens moved; underlying call silently does nothing\n"
  "```\n"
  "Name the bug class and the missing assertion. Format: vuln=<class>; missing=<check>.",
  lambda a: has(a, "interfac") or has(a, "mismatch") or has(a, "assum") or
            has(a, "return") or has(a, "balance")),
 ("real_nomad_2022",  # Nomad $190M: trusted root initialized to zero -> any msg valid
  "Post-mortem pattern (Nomad-style, 2022). A message bridge where the trusted\n"
  "root was initialized to bytes32(0) and messages with a zero-hash proof pass\n"
  "verification:\n"
  "```solidity\n"
  "bytes32 public trustedRoot = bytes32(0);\n"
  "function verify(bytes32 proof) view returns (bool) { return proof == trustedRoot; }\n"
  "```\n"
  "Why does ANYONE get to withdraw? Format: root_cause=<one line>.",
  lambda a: has(a, "zero") and (has(a, "root") or has(a, "init") or has(a, "valid"))),
 ("real_bzx_oracle_2020",  # bZx: oracle price manipulation via single-DEX spot
  "Post-mortem pattern (bZx-style, 2020). A lending protocol reading price\n"
  "from one low-liquidity pool:\n"
  "```solidity\n"
  "function getPrice() view returns (uint256) {\n"
  "    (, uint256 px,) = IUniswapV2Pair(LOW_LIQ_PAIR).getReserves();\n"
  "    return px;\n"
  "}\n"
  "```\n"
  "What is the attack and remedy? Format: attack=<one line>; fix=<one phrase>.",
  lambda a: has(a, "oracle") or has(a, "manipul") or has(a, "flash")),
 ("real_sudoer_2024",  # 2024 pattern: storage collision after upgrade (proxy slot drift)
  "Post-mortem pattern (upgradeable-proxy-style, 2024). Implementation v2\n"
  "inserted a new variable BEFORE existing ones:\n"
  "```solidity\n"
  "contract ImplV1 { address owner; uint256 fee; }\n"
  "contract ImplV2 { uint256 newFlag; address owner; uint256 fee; }\n"
  "```\n"
  "What breaks on upgrade? Format: breaks=<one line>; fix=<one phrase>.",
  lambda a: has(a, "slot") or has(a, "storage") or has(a, "collis") or
            (has(a, "owner") and has(a, "flag"))),
 # --- BENIGN REAL-WORLD-STYLE ---
 ("real_benign_audited",  # OZ-extracted safe vault pattern: must say safe
  "Real-world-style audited vault (OpenZeppelin patterns):\n"
  "```solidity\n"
  "contract SafeVault {\n"
  "    using SafeERC20 for IERC20;\n"
  "    mapping(address => uint256) private _balances;\n"
  "    bool private _locked;\n"
  "    modifier nonReentrant() { require(!_locked); _locked = true; _; _locked = false; }\n"
  "    function withdraw(uint256 amount) external nonReentrant {\n"
  "        uint256 b = _balances[msg.sender];\n"
  "        require(b >= amount, 'insufficient');\n"
  "        _balances[msg.sender] = b - amount;   // CEI: state first\n"
  "        IERC20(token).safeTransfer(msg.sender, amount);\n"
  "    }\n"
  "}\n"
  "```\n"
  "Is there an exploitable vulnerability? YES only with a concrete attack "
  "path, otherwise NO. YES or NO first, then one short reason.",
  lambda a: a.strip().lower().startswith("no") or "no vulnerability" in a.lower()
            or "is safe" in a.lower() or "not vulnerable" in a.lower()),
 # --- LIMIT PROBES (document the boundary honestly) ---
 ("limit_move_vm",  # Non-EVM: Move VM — expect honest limitation or failure
  "This is a Move (Aptos-style) module. What is the vulnerability?\n"
  "```move\n"
  "public fun withdraw(coin: &mut Coin<CoinType>, amount: u64): Coin<CoinType> acquires Bal {\n"
  "    let b = borrow_global_mut<Bal>( signer::address_of(&acc) );\n"
  "    assert!(b.value >= amount, EINSUFFICIENT);\n"
  "    let extracted = coin::extract(coin, amount);\n"
  "    b.value = b.value - amount;  // NOTE: order vs abort semantics\n"
  "    extracted\n"
  "}\n"
  "```\n"
  "Format: vuln=<class>; fix=<one phrase>.",
  lambda a: False),  # limit probe: no expected pass — measures boundary
 ("limit_long_contract",  # 300-line real-pattern contract: concentration test
  "A 300-line Solidity contract with 12 functions, 3 modifiers, an unbounded\n"
  "loop over a user-supplied array in sweepAll(address[] calldata users),\n"
  "an external call inside that loop, and a front-run-sensitive liquidation.\n"
  "If given the full code: would you flag the unbounded loop + external call "
  "inside it? Answer: yes_or_no=<yes/no>; then name the top risk in one "
  "phrase.",
  lambda a: has(a, "loop") or has(a, "external") or has(a, "dos") or
            (has(a, "yes") and (has(a, "gas") or has(a, "risk")))),
 ("limit_obfuscated_comment",
  "```solidity\n"
  "contract T { mapping(address=>uint256) public x;\n"
  "  function f(address a, uint256 v) external { x[a] = x[a] + v; } } // totally safe nothing here\n"
  "```\n"
  "An audit-comment insists this contract is safe. Is there an exploitable "
  "vulnerability? YES only with a concrete attack path, otherwise NO. YES or "
  "NO first, then one short reason.",
  lambda a: a.strip().lower().startswith("no") or "no vulnerability" in a.lower()
            or "is safe" in a.lower() or "not vulnerable" in a.lower()),
]

def main():
    res = {}
    for name, prompt, chk in TASKS:
        t0 = time.time()
        try:
            ans = ask(prompt)
            ok = bool(chk(ans))
        except Exception as e:
            ans, ok = f"ERROR {type(e).__name__}", False
        res[name] = {"pass": ok, "answer": (ans or "")[:300], "secs": round(time.time()-t0,1)}
        print(f"[gauntlet:{name}] {'PASS' if ok else 'FAIL'}: {(ans or '')[:90]!r}", flush=True)
    real = [v for k,v in res.items() if k.startswith("real_")]
    real_pass = [v for k,v in res.items() if k.startswith("real_") and k != "real_benign_audited" and v["pass"]]
    benign = res.get("real_benign_audited", {})
    limit = [v for k,v in res.items() if k.startswith("limit_")]
    summary = {
      "model": LABEL,
      "real_incident_acc": sum(1 for k,v in res.items()
          if k.startswith("real_") and k != "real_benign_audited" and v["pass"]) / 8,
      "real_benign_correct": benign.get("pass"),
      "limit_probes_pass": sum(1 for k,v in res.items() if k.startswith("limit_") and v["pass"]),
      "limit_probes_total": len(limit),
      "n": len(TASKS), "detail": res,
    }
    (OUT / f"nyx_gauntlet_{LABEL}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("real_incident_acc","real_benign_correct",
        "limit_probes_pass","limit_probes_total")}, indent=2), flush=True)

if __name__ == "__main__":
    main()