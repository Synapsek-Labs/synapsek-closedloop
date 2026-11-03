# EVDGT kill-test trainer (pre-reg EVDGT_PREREG.md, frozen 2026-11-03).
# Arms: U = fresh uniform 186-row draw; D = dynamic frontier (re-probe every
# segment, select rows in the model's CURRENT 20-50% pass-rate band).
# Total budget matched to bandsamp: 186 pair-presentations x 2 epochs = 372 steps.
# Run on shinobi (spark-venv): python scripts\evdgt_train.py <U|D> <seed 1|2|3>
import json, random, sys, io, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

ARM = sys.argv[1].upper() if len(sys.argv) > 1 else "U"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 1
assert ARM in ("U", "D")

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
POOL = NODE / "bandsamp_pool.jsonl"
MODEL_DIR = r"C:\Users\User\hf_models\nyx-2-joint-v3"
OUT = NODE / "evdgt" / f"{ARM}_s{SEED}"
LR = 5e-5
EPOCHS = 2
MAXLEN = 2048
R = 16
SEGMENTS = 3           # 3 x 62 pairs x 2 epochs = 372 steps
K = 3
BATCH = 8
MAXNEW = 256
FRONTIER = (0.2, 0.5)  # EVDGT moving frontier


def norm(messages):
    out = []
    for m in messages:
        m = dict(m)
        tcs = m.get("tool_calls")
        if tcs is None:
            m.pop("tool_calls", None)
        else:
            for tc in tcs:
                a = tc["function"]["arguments"]
                tc["function"]["arguments"] = (json.loads(a)
                                               if isinstance(a, str) else a)
        out.append(m)
    return out


def render(tok, prefix_msgs):
    return tok.apply_chat_template(prefix_msgs, tokenize=False,
                                   add_generation_prompt=True)


def score(gen_text, tgt_msg, tgt_tools):
    g = " ".join(gen_text.lower().split())
    if tgt_tools:
        return tgt_tools[0].lower() in g
    t = " ".join((tgt_msg.get("content") or "").lower().split())[:300]
    return len(t) >= 8 and t in g


def probe_pool(tok, model, sel_rows):
    """k=3 rates for each pool row against the CURRENT model (with adapter)."""
    model.eval()
    rates = []
    t0 = time.time()
    for bstart in range(0, len(sel_rows), BATCH):
        batch = sel_rows[bstart:bstart + BATCH]
        prompts = [render(tok, r["prefix"]) for r in batch]
        enc = tok(prompts, return_tensors="pt", padding=True,
                  truncation=True, max_length=MAXLEN).to("cuda:0")
        with torch.no_grad():
            gen = model.generate(**enc, do_sample=True, temperature=0.7,
                                 top_p=0.9, top_k=None,
                                 num_return_sequences=K, max_new_tokens=MAXNEW,
                                 pad_token_id=tok.eos_token_id)
        plen = enc["input_ids"].shape[1]
        for j, r in enumerate(batch):
            hits = 0
            for k in range(K):
                txt = tok.decode(gen[j * K + k][plen:], skip_special_tokens=True)
                if score(txt, r["target"], r.get("tgt_tools") or []):
                    hits += 1
            rates.append(hits / K)
        if (bstart // BATCH) % 20 == 0:
            print(f"  [probe] {bstart + len(batch)}/{len(sel_rows)} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    model.train()
    return rates


def frontier_select(rows, rates, n_target):
    """Select rows inside the 20-50% band; top-up with closest-to-band rows."""
    lo, hi = FRONTIER
    inside = [i for i, r in enumerate(rates) if lo <= r <= hi]
    rest = sorted((i for i in range(len(rows)) if i not in inside),
                  key=lambda i: 0 if rates[i] < lo else rates[i] - hi)
    order = inside + rest
    return [rows[i] for i in order[:n_target]], len(inside)


def to_pairs(tok, sel):
    pairs, skipped = [], 0
    for r in sel:
        msgs = list(r["prefix"]) + [dict(r["target"])]
        prompt = tok.apply_chat_template(msgs[:-1], tokenize=False,
                                         add_generation_prompt=True)
        full = tok.apply_chat_template(msgs, tokenize=False)
        p = commonprefix([prompt, full])
        if len(p) < len(prompt) - 16:
            skipped += 1
            continue
        tgt = full[len(p):]
        if tgt.strip():
            pairs.append((p, tgt))
    return pairs, skipped


def main():
    random.seed(SEED * 7919 + 13)  # fresh draw seeds, disjoint from bandsamp A
    torch.manual_seed(SEED * 7919 + 13)
    rows = [json.loads(l) for l in
            POOL.read_text(encoding="utf-8").splitlines() if l.strip()]
    band = [r for r in rows if 0.0 < r["rate"] < 1.0]
    n = len(band)
    print(f"[ev-{ARM}s{SEED}] pool={len(rows)} band={n}", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    model.eval()
    cfg = LoraConfig(r=R, lora_alpha=2 * R, lora_dropout=0.05,
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, cfg)
    model.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=LR)

    t0 = time.time()
    step = 0
    for seg in range(SEGMENTS):
        if ARM == "U":
            sel = random.sample(rows, n // SEGMENTS)
        else:
            if seg == 0:
                sel, inband = band[:n // SEGMENTS], n
            else:
                print(f"[ev-{ARM}s{SEED}] RE-PROBE segment {seg}", flush=True)
                rates = probe_pool(tok, model, rows)
                sel, inband = frontier_select(rows, rates,
                                              n // SEGMENTS)
                print(f"[ev-{ARM}s{SEED}] frontier rows in 20-50%: {inband}, "
                      f"selected {len(sel)}", flush=True)
        pairs, skipped = to_pairs(tok, sel)
        random.shuffle(pairs)
        print(f"[ev-{ARM}s{SEED}] seg{seg}: {len(pairs)} pairs "
              f"({skipped} skipped)", flush=True)
        for ep in range(EPOCHS):
            tot = 0.0
            for prompt, target in pairs:
                p_ids = tok(prompt, return_tensors="pt", truncation=True,
                            max_length=MAXLEN).input_ids.to("cuda:0")
                full = tok(prompt + target, return_tensors="pt",
                           truncation=True, max_length=MAXLEN).input_ids.to("cuda:0")
                labels = full.clone()
                labels[:, :p_ids.shape[1]] = -100
                out = model(input_ids=full, labels=labels)
                out.loss.backward()
                opt.step(); opt.zero_grad()
                tot += out.loss.item()
                step += 1
                if step % 100 == 0:
                    print(f"[ev-{ARM}s{SEED}] seg{seg} step {step} "
                          f"loss~{tot / 100:.3f} ({time.time() - t0:.0f}s)",
                          flush=True)
                    tot = 0.0

    OUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUT))
    tok.save_pretrained(str(OUT / "tokenizer"))
    print(f"[ev-{ARM}s{SEED}] DONE {step} steps -> {OUT} "
          f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
