# NYX CORE 8B — PRE-REGISTERED TARGET BARS (frozen 2026-11-02, before training)
Base: Qwen3-8B (Apache-2.0). Method: QLoRA SFT on execution-verified agentic data (+ optional RL pass).
- Function calling (BFCL v4 class): > 46.7
- SWE-bench Verified class: > 24.1
- Terminal-agent class: > 13.0
- Code (LiveCodeBench v5 class): > 23.5
Verdict rule: SHIP only if all four exceed; report honest nulls otherwise.
