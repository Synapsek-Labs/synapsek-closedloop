# NYX CORE 8B — PRE-REGISTRATION (frozen BEFORE any data/training, 2026-11-01)

## Mission (user directive)
Generalist agent/engineer model: top agentic skills, tool use, coding for developers.
NOT a security model. Cybersecurity verticals come after Core 8B AND Pro 27-30B complete.

## Base candidates (chosen by measurement, 40-70% band law)
qwen3-8b-normal vs dsr1-8b-normal (both local, 4-bit measured). Pick: highest in-band
composite; if both >70% on a gate, that gate is "already solved" and gets harder tasks;
if both <40%, the gate's data recipe gets rebuilt before training.

## PRE-REGISTERED GATES (bars frozen now)
- G1 FUNCTION-CALLING: 10 tool-use prompts, OpenAI tools format. PASS bar for the
  TRAINED model: >=8/10 valid JSON tool call with correct tool + all required args.
- G2 CODE CORRECTNESS: 20 fixed Python problems, execution-verified (tests run, temp 0.2,
  2 attempts). TRAINED bar: >=14/20 (70%) pass rate.
- G3 AGENT TOOL-TASKS: 10 of our office battery tasks via terminal-tool loop (server
  mode). TRAINED bar: >=7/10 (70%).
- G4 BASE BAND (measurement-only): composite of G1+G2 on both candidate bases. Trainable
  domain = 40-70%. Documented regardless of outcome.

## Data recipe (open-weight sources only; NEVER frontier-API outputs - ToS law)
1. Open function-calling SFT corpora (e.g. glaive-fn-calling style, ToolACE style)
2. Code-instruct with execution verification (only problems the generator solved)
3. Our Hebri-verified tool trajectories (generic agent skill, execution-verified)
4. Curation rules: dedupe, license check per dataset (permissive GO / NC careful /
   frontier NO), executable code only, format = chat template of the chosen base.
Target: 20k-40k rows mixed, then 2-3 epochs QLoRA r16 on the 5090 (~$0).

## Success definition
Nyx Core 8B >= bars on G1-G3 AND >= qwen3-8b base on every gate (no regression) AND
beats the 1.7B joint-v3 on office battery (bigger brain must win its own game).
