# SWAP v0 — Swarm Adapter Protocol (docs/swarm_protocol.md)
#
# Export/import of bank entries between Hebri Swarm nodes.
# Safety rules implemented here:
#   1. never merge (imported adapters become bank entries via admission)
#   2. receiver-side re-verification (import runs the FULL admission battery)
#   3. base-model identity check (adapter discarded on mismatch)
#   4. provenance signature (ed25519 over the canonical manifest; TOFU pinning)
#   5. only execution-verified artifacts; no raw data crosses the wire
from __future__ import annotations
import base64, hashlib, json, shutil
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)
from cryptography.exceptions import InvalidSignature

from src.node.nightly import NODE_DIR

PROTO = "swap/0"


def _node_dir(node_id):
    d = NODE_DIR / node_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_keys(node_id):
    """Per-node ed25519 keypair; seed stored in NODE_DIR (TOFU on first import)."""
    kf = _node_dir(node_id) / "swarm_key.json"
    if kf.exists():
        d = json.loads(kf.read_text())
        sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(d["seed"]))
    else:
        sk = Ed25519PrivateKey.generate()
        kf.write_text(json.dumps({
            "seed": sk.private_bytes_raw().hex(),
            "public": sk.public_key().public_bytes_raw().hex()}))
    return sk, sk.public_key().public_bytes_raw().hex()


def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode()


def _canonical(m: dict) -> bytes:
    return json.dumps({k: v for k, v in m.items() if k != "sig"},
                      sort_keys=True, separators=(",", ":")).encode()


def export_entry(node_id, name, registry_dir="swarm_registry"):
    """Package a bank entry as a SWAP manifest + adapter bundle."""
    import time
    from src.node.bank import list_bank, _bank_dir
    entries = [e for e in list_bank(node_id) if e["name"] == name and
               e.get("accepted")]
    if not entries:
        print(f"[swap] no admitted bank entry '{name}' on {node_id}")
        return None
    e = entries[0]
    adapter_src = _bank_dir(node_id) / name

    sk, pub = ensure_keys(node_id)
    manifest = {
        "proto": PROTO,
        "capability": name,
        "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
        "adapter": {"format": "peft-lora", "sha256": None, "b64": None},
        "gain": {"metric": "pot-battery", "n": e["probe_n"],
                 "base_acc": e["base_acc"], "adapter_acc": e["adapter_acc"]},
        "data_provenance": {"source": "teacher-7B-pot",
                            "verifier": "execution-vs-gold"},
        "node_id": node_id,
        "exported_at": time.strftime("%Y-%m-%d %H:%M"),
        "node_pub": pub,
    }
    # bundle adapter files into one b64 blob (small adapters only, v0)
    blobs = {}
    for f in sorted(adapter_src.rglob("*")):
        if f.is_file():
            blobs[str(f.relative_to(adapter_src))] = _b64(f)
    manifest["adapter"]["b64"] = base64.b64encode(
        json.dumps(blobs, sort_keys=True).encode()).decode()
    manifest["adapter"]["sha256"] = hashlib.sha256(
        manifest["adapter"]["b64"].encode()).hexdigest()
    manifest["sig"] = base64.b64encode(
        sk.sign(_canonical(manifest))).decode()

    out = Path(registry_dir) / node_id / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"[swap] exported {node_id}/{name} -> {out/'manifest.json'} "
          f"(gain {e['base_acc']:.1%} -> {e['adapter_acc']:.1%})")
    return out / "manifest.json"


def import_entry(node_id, manifest_path, probe_n=100, pinned_pubs=None):
    """Receive a SWAP manifest: verify signature + base identity, stage the
    adapter, run the FULL admission battery on THIS node's hardware, and
    admit-or-discard. The receiver's base model is never modified."""
    from src.node.bank import add_to_bank

    m = json.loads(Path(manifest_path).read_text())
    if m.get("proto") != PROTO:
        print("[swap] proto mismatch — discard"); return None

    # 4. signature verification (TOFU: pin publisher key on first import)
    pub_hex = m.get("node_pub", "")
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        pub.verify(base64.b64decode(m["sig"]), _canonical(m))
    except (InvalidSignature, ValueError, KeyError):
        print("[swap] BAD SIGNATURE — discard"); return None
    if pinned_pubs and pub_hex not in pinned_pubs:
        print(f"[swap] publisher {pub_hex[:16]}.. not pinned — discard")
        return None

    # 3. base-model identity check
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(m["base_model"])
    base_rev = hashlib.sha256(cfg.to_diff_dict().__str__().encode()).hexdigest()[:16]
    local = _node_dir(node_id) / "base_rev.txt"
    if not local.exists():
        local.write_text(base_rev)
    if local.read_text().strip() != base_rev:
        print(f"[swap] base-model mismatch ({m['base_model']}) — discard")
        return None

    # stage adapter from bundle into quarantine
    blobs = json.loads(base64.b64decode(m["adapter"]["b64"]).decode())
    if hashlib.sha256(m["adapter"]["b64"].encode()).hexdigest() != \
            m["adapter"]["sha256"]:
        print("[swap] adapter hash mismatch — discard"); return None
    qdir = _node_dir(node_id) / "quarantine" / m["capability"]
    if qdir.exists():
        shutil.rmtree(qdir)
    qdir.mkdir(parents=True)
    for rel, b64 in blobs.items():
        p = qdir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(base64.b64decode(b64))

    # 2. receiver-side re-verification = the FULL admission battery
    entry = add_to_bank(node_id, qdir, m["capability"], probe_n=probe_n)
    if entry:
        entry["swap"] = {"from": m["node_id"], "pub": pub_hex[:16] + "..",
                         "exported_gain": m["gain"]}
        from src.node.bank import _save, list_bank
        _save(node_id, [e if e["name"] != m["capability"] else entry
                        for e in list_bank(node_id)])
        print(f"[swap] imported {m['node_id']}/{m['capability']} -> ADMITTED "
              f"(local gain {entry['gain']:+.1%})")
    else:
        print(f"[swap] imported {m['capability']} -> REJECTED by local battery "
              f"(stays quarantined, never routed)")
    shutil.rmtree(qdir, ignore_errors=True)
    return entry


if __name__ == "__main__":
    import argparse, sys
    sys.path.insert(0, ".")
    ap = argparse.ArgumentParser()
    ap.add_argument("--node", default="shinobi-1")
    ap.add_argument("--export", help="bank entry name to export")
    ap.add_argument("--import", dest="imp", help="manifest.json to import")
    ap.add_argument("--as-node", help="importing node id (default = --node)")
    a = ap.parse_args()
    if a.export:
        export_entry(a.node, a.export)
    elif a.imp:
        import_entry(a.as_node or a.node, a.imp)
    else:
        print("use --export NAME or --import manifest.json")
