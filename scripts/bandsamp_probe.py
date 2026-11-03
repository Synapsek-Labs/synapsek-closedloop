# Band-sampling kill-test STEP 1: pass@k probe (pre-registration d8a0ec7).
# Estimates per-example correctness rate of nyx-2-joint-v3 on bank pairs:
# k=3 samples (temp 0.7), cheap symmetric scorer. Band = 0 < rate < 1.
# Run on shinobi (spark-venv, local GPU batch generation alongside :8001 server):
#   spark-venv\Scripts\python.exe scripts\bandsamp_probe.py [N_POOL]
# Writes runs/node/shinobi-1/bandsamp_pool.jsonl  (one line: bank, prompt, target, rate)
import json, random, sys, io, time
from os.path import commonprefix
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

REPO = Path(__file__).resolve().parents[1]
NODE = REPO / "runs" / "node" / "shinobi-1"
DATA = [NODE / "work_office.jsonl", NODE / "work_office_v2.jsonl",
        NODE / "work_sec21.jsonl", NODE / "work_sec22.jsonl",
        NODE / "work_audit.jsonl", NODE / "work_audit2.jsonl"]
MODEL_DIR = r"C:\Users\User\hf_models\nyx-2-joint-v3"
OUT = NODE / "bandsamp_pool.jsonl"
K = 3
POOL_N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
BATCH = 8
MAXNEW = 256
MAXLEN = 2048


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


def build_pairs():
    per_bank = {}
    for f in DATA:
        if f.exists():
            per_bank[f.name] = []
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                msgs = norm(r["messages"])
                # last assistant turn = the verified target
                idx = [i for i, m in enumerate(msgs) if m["role"] == "assistant"]
                if not idx:
                    continue
                i = idx[-1]
                if i == 0:
                    continue
                tgt_tools = [tc["function"]["name"] for tc in
                             (msgs[i].get("tool_calls") or [])]
                per_bank[f.name].append((msgs[:i], msgs[i], tgt_tools))
    return per_bank


def main():
    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, device_map="cuda:0",
        trust_remote_code=True)
    model.eval()

    per_bank = build_pairs()
    total = sum(len(v) for v in per_bank.values())
    print(f"[probe] bank rows with assistant target: {total}", flush=True)
    # stratified round-robin sample of POOL_N across banks
    pools = {k: list(v) for k, v in per_bank.items()}
    sel = []
    while len(sel) < POOL_N and any(pools.values()):
        for k in list(pools):
            if pools[k] and len(sel) < POOL_N:
                sel.append((k, pools[k].pop(random.Random(len(sel)).randrange(len(pools[k])))))
    print(f"[probe] probed pool: {len(sel)}", flush=True)

    def render_prefix(prefix_msgs):
        return tok.apply_chat_template(prefix_msgs, tokenize=False,
                                       add_generation_prompt=True)

    def score(gen_text, tgt_msg, tgt_tools):
        g = " ".join(gen_text.lower().split())
        if tgt_tools:
            return tgt_tools[0].lower() in g
        t = " ".join((tgt_msg.get("content") or "").lower().split())
        t = t[:300]
        return len(t) >= 8 and t in g

    t0 = time.time()
    n_done = 0
    with open(OUT, "w", encoding="utf-8") as out_f:
        for bstart in range(0, len(sel), BATCH):
            batch = sel[bstart:bstart + BATCH]  # items: (bank, (prefix_msgs, tgt_msg, tgt_tools))
            prompts = [render_prefix(item[1][0]) for item in batch]
            enc = tok(prompts, return_tensors="pt", padding=True,
                      truncation=True, max_length=MAXLEN).to("cuda:0")
            with torch.no_grad():
                gen = model.generate(**enc, do_sample=True, temperature=0.7,
                                     top_p=0.9, num_return_sequences=K,
                                     max_new_tokens=MAXNEW,
                                     pad_token_id=tok.eos_token_id)
            plen = enc["input_ids"].shape[1]
            for j, (bank, (prefix_msgs, tgt_msg, tgt_tools)) in enumerate(batch):
                hits = 0
                for k in range(K):
                    txt = tok.decode(gen[j * K + k][plen:], skip_special_tokens=True)
                    if score(txt, tgt_msg, tgt_tools):
                        hits += 1
                out_f.write(json.dumps({
                    "bank": bank,
                    "prefix": [dict(m) for m in prefix_msgs],
                    "target": dict(tgt_msg),  # incl. verified tool_calls (dict args)
                    "tgt_tools": tgt_tools,
                    "rate": hits / K,
                }, ensure_ascii=False) + "\n")
            n_done += len(batch)
            el = time.time() - t0
            print(f"[probe] {n_done}/{len(sel)} rows ({el:.0f}s, "
                  f"{el / max(n_done, 1):.1f}s/row)", flush=True)
    print(f"[probe] DONE -> {OUT} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()