# bank_smoke.py — end-to-end bank plumbing test on a GPU pod (cheap burst)
#
# Exercises: student-generated verified programs -> tiny replay-mix adapter
# -> add_to_bank (probe gate) -> route -> load_routed (wrapped, NOT merged)
# -> registry re-add semantics. Uses small n everywhere; NOT a science run.
import json, random, sys, time
from pathlib import Path

sys.path.insert(0, ".")
import torch
from src.node.pot_node import (_ensure_split, eval_pot, _gen_replay,
                               train_student_pot, POT_PROMPT)
from src.loop.pot_runner import run_one
from src.loop.synthesizer import _extract_code
from src.cartography.battery import extract_last_number

N_TASKS = 24
REPLAY_N = 24

def main():
    tok, model = load_student()
    tok.padding_side = "left"
    pool, held = _ensure_split()
    rng = random.Random(3)
    work = rng.sample(pool, N_TASKS)

    # student generates its own programs; keep execution-verified ones
    rows = []
    B = 8
    for i in range(0, len(work), B):
        chunk = work[i:i + B]
        prompts = [POT_PROMPT.format(q=t["question"]) for t in chunk]
        ids = tok(prompts, return_tensors="pt", padding=True,
                  truncation=True, max_length=1024).to("cuda:0")
        out = model.generate(**ids, max_new_tokens=512, do_sample=False,
                             pad_token_id=tok.pad_token_id or tok.eos_token_id)
        for j, t in enumerate(chunk):
            text = tok.decode(out[j][ids["input_ids"].shape[1]:],
                              skip_special_tokens=True)
            code = _extract_code(text)
            if not code:
                continue
            ok, number = run_one(code)
            gold = extract_last_number(t["answer"])
            if ok and number is not None and gold is not None and \
                    abs(number - gold) < 1e-4:
                rows.append({"id": t["id"], "question": t["question"],
                             "answer": t["answer"], "program": code})
        print(f"[smoke] {i+B}/{len(work)} tasks, {len(rows)} verified",
              flush=True)
    print(f"[smoke] {len(rows)} verified student programs", flush=True)
    if len(rows) < 8:
        print("[smoke] too few verified — SKIPPING train, still testing bank"
              " admission with a null adapter", flush=True)
        rows = rows or []

    # tiny adapter via the validated recipe (small n)
    import src.node.pot_node as pn
    import src.node.nightly as nightly
    nightly.NODE_DIR = Path("runs/node")
    pn.NODE_DIR = nightly.NODE_DIR
    (pn.NODE_DIR / "smoke-1").mkdir(parents=True, exist_ok=True)
    if rows:
        tok2 = tok
        ad_dir = Path("runs/node/smoke-1/delta_smoke")
        # manual tiny training (replay mix), to keep this a SMOKE not science
        replay = _gen_replay(model, tok2, n=REPLAY_N)
        pairs = [(POT_PROMPT.format(q=r["question"]), r["program"]) for r in rows] + replay
        random.shuffle(pairs)
        from peft import LoraConfig, get_peft_model
        cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                         target_modules=["q_proj", "v_proj"])
        pm = get_peft_model(model, cfg)
        pm.train()
        opt = torch.optim.AdamW([p for p in pm.parameters() if p.requires_grad],
                                lr=5e-5)
        for step, (prompt, target) in enumerate(pairs):
            p_ids = tok(prompt, return_tensors="pt", truncation=True,
                        max_length=512).input_ids.to("cuda:0")
            full = tok(prompt + target, return_tensors="pt", truncation=True,
                       max_length=1024).input_ids.to("cuda:0")
            labels = full.clone(); labels[:, :p_ids.shape[1]] = -100
            out = pm(input_ids=full, labels=labels)
            out.loss.backward(); opt.step(); opt.zero_grad()
            if (step + 1) % 10 == 0:
                print(f"[smoke] train {step+1}/{len(pairs)} "
                      f"loss={out.loss.item():.3f}", flush=True)
        pm.save_pretrained(str(ad_dir))
        del pm
        torch.cuda.empty_cache()

    # BANK: admission with probe gate
    from src.node.bank import add_to_bank, route, load_routed, list_bank
    e = add_to_bank("smoke-1", "runs/node/smoke-1/delta_smoke", "smoke",
                    probe_n=16)
    print("[smoke] registry:", json.dumps(list_bank("smoke-1")), flush=True)
    r = route("smoke-1")
    print("[smoke] route ->", r, flush=True)
    tok3, m3, entry = load_routed("smoke-1")
    is_peft = "PeftModel" in type(m3).__name__
    print(f"[smoke] load_routed: peft={is_peft}, entry={entry}", flush=True)
    assert is_peft == (entry is not None)
    print("[smoke] ALL BANK PATHS OK", flush=True)


def load_student():
    from experiments.run_longhorizon_demo import load_model
    return load_model()


if __name__ == "__main__":
    main()