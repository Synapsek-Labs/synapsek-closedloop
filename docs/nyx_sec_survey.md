# Nyx-Sec — open-model survey for the security/audit line (2026-10-29)

Scope: professional, AUTHORIZED penetration testing / red-teaming /
defensive audit use only. Synapsek ships capability for professionals;
engagement authorization is the user's responsibility, as with any
security tooling. Surveyed 2026-10-29.

## Abliterated/uncensored availability (huihui-ai = the main publisher)

| Base (license) | Uncensored artifact | Notes |
|---|---|---|
| DeepSeek-R1-Distill-Qwen-1.5B (MIT) | huihui-ai/...-abliterated | matches our Nyx-1 size class |
| DeepSeek-R1-0528-Qwen3-8B (MIT) | huihui-ai abliterated + Heretic build (89→4 refusals, KL 0.041) | Heretic = better method than crude ablation |
| DeepSeek-R1-Distill-Qwen-32B (MIT) | huihui-ai abliterated | teacher-class |
| Qwen3.8-27B (Apache-2.0) | huihui-ai abliterated (+GGUF, 2.5M downloads) | user's named model |
| Qwen3-Coder-30B-A3B MoE (Apache-2.0) | huihui-ai abliterated | 3.3B active — code-native, tool-calling |
| GLM-4.5-Air / 4.5V (MIT) | huihui-ai abliterated (+GGUF/MLX) | exists |
| DeepSeek-V4-Flash-Vision (284B MoE) | huihui-ai abliterated GGUF | frontier-class, streaming/colibri territory |
| Qwen3.8-Flash-Next (177B MoE) | huihui-ai abliterated GGUF | colibri-listed engine |

Normal (censored) versions are the official HF originals; every
abliterated artifact above names its base — we ship BOTH tiers:
"Nyx-Sec" (base + verified security adapters) and "Nyx-Sec-U"
(abliterated base + same adapters).

Better-than-abliteration option: Heretic (p-e-w) — automated refusal
direction removal with KL-drift minimization; we can run it ourselves
on any Apache/MIT base we adopt, keeping provenance in our hands.

## Cybersecurity fine-tunes that already exist (the competition)

- HIDra-30B-A3B (SAPSAN): abliterated Qwen3-Coder-30B + red-team SFT,
  offline GGUF, Apache-2.0. Proves demand + feasibility.
- DeepHat V2 (WhiteRabbitNeo): Qwen2.5-Coder 7B/32B + 1.7M
  offensive/defensive samples.
- pentest-v2: Qwen3-8B LoRA on GTFOBins/HackTricks/HTB writeups —
  GTFOBins 100% vs 25% base.

## The Synapsek angle nobody in this list has

All of these are curated-data SFT (static knowledge, unverifiable
claims). Our recipe is EXECUTION-VERIFIED: a pentest PoC/exploit is
correct iff it runs against the target sandbox and produces the
declared effect. Security tasks are the most execution-verifiable
domain there is:

- CTF challenges: flag either found or not — objective gate.
- PoC scripts: executed in an isolated sandbox vs vulnerable fixture.
- Tool workflows: nmap/metasploit/nuclei invocations verified by
  tool exit codes and parsed outputs.

=> Nyx-Sec plan: take the best Apache/MIT abliterated-or-Heretic base
(Qwen3-Coder-30B-A3B is the leading candidate: MoE, code-native,
3.3B active = fast), build an EXECUTION-VERIFIED pentest corpus
(CTF + sandboxed PoC + tool-use), apply the same
replay-anchor/bank/admission stack. Result: a security model whose
knowledge is proven to run, not scraped from writeups — and the swarm
lets every professional node contribute verified findings without
leaking client data (trajectories stay local; only verified,
synthetic-target artifacts leave).

## Download shortlist (for evaluation on shinobi/pods)

1. huihui-ai/Huihui-Qwen3-Coder-30B-A3B-Instruct-abliterated (base for Nyx-Sec eval)
2. huihui-ai/Huihui-Qwen3.8-27B-abliterated (dense 27B comparison)
3. deepseek-ai/DeepSeek-R1-0528-Qwen3-8B (normal) + Heretic 8B build (uncensored pair)
4. huihui-ai/DeepSeek-R1-Distill-Qwen-1.5B-abliterated (Nyx-1-size pairing)
