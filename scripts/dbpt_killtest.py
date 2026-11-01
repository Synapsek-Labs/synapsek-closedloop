# DBPT kill-test trainer — two identical tiny GPTs, baseline vs 40-70% loss-band masking.
# Pre-registration: docs/DBPT_KILLTEST_PREREG.md. Runs on shinobi 5090 (needs ~10GB total).
import json, math, os, sys, time, urllib.request, zipfile
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import GPT2TokenizerFast

NODE = Path(r"C:\Users\User\synapsek-closedloop\runs\node\shinobi-1")
DATA_DIR = NODE / "dbpt_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CKPT = NODE / "dbpt_runs"
CKPT.mkdir(exist_ok=True)
DEV = "cuda"
STEPS = int(os.environ.get("DBPT_STEPS", "60000"))
BS, SEQ = 16, 512
BAND_LO, BAND_HI = 0.40, 0.70

# ---------------- data ----------------
def get_text():
    f = DATA_DIR / "wikitext103.txt"
    if not f.exists() or f.stat().st_size < 50_000_000:
        url = "https://wikitext.s3.amazonaws.com/repositories/wikitext-103-raw-v1.zip"
        z = DATA_DIR / "wt.zip"
        if not z.exists():
            urllib.request.urlretrieve(url, z)
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.endswith("wiki.test.raw"):
                    with zf.open(n) as src, open(DATA_DIR / "val.txt", "wb") as dst:
                        dst.write(src.read())
                if n.endswith("wiki.train.raw"):
                    with zf.open(n) as src, open(f, "wb") as dst:
                        dst.write(src.read())
    return f.read_text(encoding="utf-8", errors="replace")

def load_tokens(tok, text):
    c = DATA_DIR / "train_ids.pt"
    if c.exists():
        return torch.load(c)
    ids = []
    B = 200_000
    for i in range(0, len(text), B):
        ids.extend(tok(text[i:i+B])["input_ids"])
    t = torch.tensor(ids, dtype=torch.long)
    torch.save(t, c)
    return t

def get_val_tokens(tok):
    c = DATA_DIR / "val_ids.pt"
    if c.exists():
        return torch.load(c)
    v = (DATA_DIR / "val.txt").read_text(encoding="utf-8", errors="replace")[:2_000_000]
    t = torch.tensor(tok(v)["input_ids"], dtype=torch.long)
    torch.save(t, c)
    return t

# ---------------- model ----------------
class Block(nn.Module):
    def __init__(s, d, h):
        super().__init__()
        s.ln1 = nn.LayerNorm(d); s.attn = nn.MultiheadAttention(d, h, batch_first=True)
        s.ln2 = nn.LayerNorm(d)
        s.mlp = nn.Sequential(nn.Linear(d, 4*d), nn.GELU(), nn.Linear(4*d, d))
    def forward(s, x):
        n = x.shape[1]
        mask = torch.triu(torch.ones(n, n, device=x.device, dtype=torch.bool), 1)
        h = s.ln1(x)
        a, _ = s.attn(h, h, h, attn_mask=mask, need_weights=False)
        x = x + a
        return x + s.mlp(s.ln2(x))

class GPT(nn.Module):
    def __init__(s, vocab, d=512, L=8, h=8):
        super().__init__()
        s.wte = nn.Embedding(vocab, d); s.wpe = nn.Embedding(SEQ, d)
        s.blocks = nn.ModuleList([Block(d, h) for _ in range(L)])
        s.lnf = nn.LayerNorm(d); s.head = nn.Linear(d, vocab, bias=False)
    def forward(s, idx):
        x = s.wte(idx) + s.wpe(torch.arange(idx.shape[1], device=idx.device))
        for b in s.blocks:
            x = b(x)
        return s.head(s.lnf(x))

# ---------------- train ----------------
def run_arm(tag, use_band, ids, val_ids, vocab):
    torch.manual_seed(1234)
    m = GPT(vocab).to(DEV, dtype=torch.bfloat16)
    opt = torch.optim.AdamW(m.parameters(), lr=3e-4, weight_decay=0.01)
    n = ids.numel()
    g = torch.Generator().manual_seed(99)
    def batch():
        starts = torch.randint(0, n - SEQ - 1, (BS,), generator=g)
        idx = torch.stack([ids[s:s+SEQ+1] for s in starts]).to(DEV)
        return idx[:, :-1], idx[:, 1:]
    def val_ppl():
        m.eval(); tot = 0.0; cnt = 0
        with torch.no_grad():
            for i in range(0, min(val_ids.numel() - SEQ - 1, SEQ*40), SEQ):
                x = val_ids[i:i+SEQ].unsqueeze(0).to(DEV)
                y = val_ids[i+1:i+SEQ+1].unsqueeze(0).to(DEV)
                lg = m(x.to(torch.bfloat16))
                tot += F.cross_entropy(lg.float().view(-1, lg.shape[-1]), y.reshape(-1),
                                        reduction="sum").item()
                cnt += y.numel()
        m.train()
        return math.exp(tot / cnt)

    hist = []
    t0 = time.time()
    for step in range(1, STEPS + 1):
        x, y = batch()
        lg = m(x)
        tok_loss = F.cross_entropy(lg.float().view(-1, lg.shape[-1]),
                                    y.reshape(-1), reduction="none")
        if use_band:
            with torch.no_grad():
                q = torch.quantile(tok_loss.detach(), torch.tensor([BAND_LO, BAND_HI]))
                mask = ((tok_loss.detach() >= q[0]) & (tok_loss.detach() <= q[1])).float()
                denom = mask.sum().clamp(min=1.0)
            loss = (tok_loss * mask).sum() / denom
        else:
            loss = tok_loss.mean()
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
        opt.step()
        if step % 5000 == 0:
            vp = val_ppl()
            tokseen = step * BS * SEQ / 1e6
            line = f"[{tag}] step {step} tok={tokseen:.0f}M train_loss={loss.item():.3f} val_ppl={vp:.3f} ({time.time()-t0:.0f}s)"
            print(line, flush=True)
            hist.append({"step": step, "val_ppl": vp, "train_loss": loss.item()})
    final = val_ppl()
    return {"arm": tag, "use_band": use_band, "steps": STEPS,
            "tokens_M": STEPS * BS * SEQ / 1e6, "final_val_ppl": final, "hist": hist}

def main():
    tok = GPT2TokenizerFast.from_pretrained("gpt2")
    text = get_text()
    ids = load_tokens(tok, text)
    val_ids = get_val_tokens(tok)
    print(f"data: {ids.numel()/1e6:.0f}M train tokens, vocab {tok.vocab_size}", flush=True)
    res = {}
    for tag, band in [("baseline", False), ("dbpt_40_70", True)]:
        print(f"=== training {tag} ===", flush=True)
        res[tag] = run_arm(tag, band, ids, val_ids, tok.vocab_size)
        (CKPT / f"dbpt_{tag}.json").write_text(json.dumps(res[tag], indent=1))
    b, d = res["baseline"]["final_val_ppl"], res["dbpt_40_70"]["final_val_ppl"]
    gain = (b - d) / b
    verdict = ("GO: DBPT wins" if gain >= 0.05 else
               ("INCONCLUSIVE" if gain >= 0 else "FAIL: DBPT worse"))
    out = {"baseline_ppl": b, "dbpt_ppl": d, "gain_pct": round(gain*100, 2),
           "rule": "GO if >=5% lower ppl", "verdict": verdict, "detail": res}
    (CKPT / "dbpt_killtest_verdict.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("baseline_ppl","dbpt_ppl","gain_pct","verdict")}, indent=1), flush=True)

if __name__ == "__main__":
    main()
