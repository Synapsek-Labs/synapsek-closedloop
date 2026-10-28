# SWARM — the Hebri node federation protocol (v0 design, 2026-10-29)

## What we are calling it

- **Product/system name: Hebri Swarm** (working name — user to confirm).
- **Protocol: SWAP — Swarm Adapter Protocol.**
- A node that participates = a **Swarm node**. A bank entry shared to the
  swarm = a **Swarm capability** (adapter + provenance + measured gain).

Rationale: Hebri's identity is the scarab (Khepri); a swarm of small
agents that exchange learned capabilities is the natural extension, and
"adapter/LoRA" stays an implementation detail behind the protocol.

## What a Swarm node is

A Hebri instance running the Learning Node v2 stack:
1. LOCAL model (frozen base, e.g. Qwen2.5-1.5B/7B) + adapter BANK.
2. Nightly collect -> execution-verified -> replay-anchored train ->
   admission gate (full battery, receiver hardware) -> bank.
3. Self-monitor (loc_cum 0.918-0.994 class) for live task triage.
4. Escalation ladder: base -> bank adapter -> bigger Swarm node ->
   (later) Synapsek-funded frontier API. No per-token API spend for
   anything a local node or the swarm can do.

## SWAP v0: what crosses the wire

A BankEntryManifest, signed by the exporting node's key:

    {
      "proto": "swap/0",
      "capability": name,
      "base_model": "Qwen/Qwen2.5-1.5B-Instruct",   # MUST match receiver
      "base_rev_sha": <tokenizer/config hash>,
      "adapter": {"format": "peft-lora", "url": ..., "sha256": ...},
      "gain": {"metric": "pot-battery", "n": 100, "seed": 7,
               "base_acc": 0.38, "adapter_acc": 0.54},
      "data_provenance": {"source": "teacher-7B-pot", "n_verified": 401,
                          "verifier": "execution-vs-gold"},
      "node_id": "shinobi-1",
      "sig": <ed25519 over the canonical manifest>
    }

## Safety rules (non-negotiable)

1. **Never merge.** Imported adapters are bank entries on the receiver;
   its base is untouched. Rejection or misbehaviour = never routed to.
2. **Receiver-side re-verification.** Exported gains are CLAIMS. The
   importer re-runs its own admission battery (n>=100, its hardware,
   its held-out slice) before first routing. No trust in transit.
3. **Base-model identity check.** Adapter applies only if base_model and
   rev hash match the receiver exactly; otherwise discard.
4. **Provenance signature.** Every manifest is signed; replay/tamper
   fails verification. (Later: Synapsek account identity as issuer.)
5. **Data hygiene.** Only execution-verified artifacts are shared; no
   raw user data ever leaves a node (trajectories stay local).

## Transport (what Hebri already gives us)

- **Pairing + authz + delivery ledger** in the Hebri gateway are the
  secure node-to-node channel; swarm manifests ride gateway peer links
  (the same path as agent-to-agent messages today).
- v0 pragmatic transport for weight files: an append-only registry
  (git repo or object store) holding manifests + adapter files; the
  gateway channel carries the notification. Weight transfer is the one
  plumbing gap (136MB adapters do not fit chat/gateway messages).
- v1: small adapters (r=16, q/v only) shrink to ~20-40MB and fit
  registry flows comfortably; prefer small capability adapters.

## Economics (v1+, rides Synapsek billing rails)

- Escalation: small node asks a bigger Swarm node for inference ->
  spender's Synapsek credits settle via the existing usage-ledger
  design (server-enforced budget, reservation/settlement; clients
  cannot self-report charges).
- Contribution: exporting an adapter that PASSES admission on N nodes
  earns credits for the trainer. The ledger already exists; swarm
  activity is just another ledger entry type.

## v0 implementation checklist (synapsek-closedloop)

- [ ] bank.py: export_entry(node, name) -> manifest + files
- [ ] bank.py: import_entry(node, manifest) -> verify sig, base match,
      stage into quarantine, run admission battery, admit-or-discard
- [ ] keypair per node (ed25519), stored in NODE_DIR
- [ ] registry layout: registry/<node>/<capability>/manifest.json +
      adapter.tgz
- [ ] test: two-node loop on shinobi (export shinobi-1 -> import
      mac-1 or pod clone) with forged/manifest-mismatch rejection
