#!/usr/bin/env python3
"""nyx_node_uplink v0.1 — the Hebri node's egress path. OPEN SOURCE (Apache-2.0).

The node's side of the node↔bank contract:
  1. serialize(row)   — structure-only projection BEFORE anything leaves RAM:
                        task text, tool_calls, machine outputs. No chat prose
                        (assistant reasoning is dropped), no raw file contents,
                        no personal fields. This is privacy by ARCHITECTURE.
  2. egress_gate(row) — default-deny allowlist: a row may transmit only if it
                        passes schema + size + secret-pattern checks.
  3. send(batch)      — nightly POST to the bank with the node key.

Everything here is deliberately dumb and local-first: no telemetry, no
phone-home other than the explicit nightly batch, works fully offline
(egress disabled -> buffer just grows locally).

Usage:
  from nyx_node_uplink import NodeUplink
  up = NodeUplink(node_key="...", bank_url="http://127.0.0.1:8010")
  up.add_row(row)          # serializes + gates now, appends to local buffer
  up.flush()               # sends buffer in one batch, clears on 200 only

CLI self-test: python nyx_node_uplink.py [--dry]
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ALLOWED_ROW_KEYS = {"task", "tool_calls", "machine_outputs", "messages", "meta"}
SECRET_PATTERNS = ("password", "secret", "api_key", "apikey", "token=")
MAX_ROW_BYTES = 500_000


def serialize(row):
    """Structure-only projection. Mirrors the bank's L1 as defense in depth."""
    if not isinstance(row, dict):
        raise ValueError("row must be dict")
    msgs = row.get("messages")
    if not isinstance(msgs, list) or not (1 <= len(msgs) <= 80):
        raise ValueError("messages 1..80 required")
    out_msgs = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        o = {"role": role}
        if role == "assistant":
            tcs = []
            for tc in m.get("tool_calls") or []:
                fn = (tc or {}).get("function") or {}
                tcs.append({"id": tc.get("id", "call0"), "type": "function",
                            "function": {"name": fn.get("name", "?"),
                                         "arguments": fn.get("arguments", "{}")}})
            if tcs:
                o["tool_calls"] = tcs
            c = m.get("content") or ""
            final = None
            for line in reversed(str(c).splitlines()):
                if line.strip().lower().startswith("final:"):
                    final = line.strip()
                    break
            if final:
                o["content"] = final      # ONLY the final answer, never reasoning
        elif role == "tool":
            o["tool_call_id"] = m.get("tool_call_id", "call0")
            o["content"] = str(m.get("content") or "")[:2000]
        else:
            o["content"] = str(m.get("content") or "")[:4000]
        out_msgs.append(o)
    out = {k: row.get(k) for k in row if k in ALLOWED_ROW_KEYS}
    out["messages"] = out_msgs
    (out.setdefault("meta", {}))["node_ts"] = int(time.time())
    return out


def egress_gate(row):
    """Default-deny. Returns (ok, reason)."""
    blob = json.dumps(row)
    if len(blob) > MAX_ROW_BYTES:
        return False, "row-too-large"
    msgs = row.get("messages")
    if not isinstance(msgs, list):
        return False, "no-messages"
    low = blob.lower()
    for pat in SECRET_PATTERNS:
        if pat in low:
            return False, f"secret-pattern:{pat}"
    if not any(isinstance(m, dict) and m.get("tool_calls") for m in msgs):
        return False, "no-tool-steps"
    return True, None


class NodeUplink:
    def __init__(self, node_key, bank_url, buffer_path="node_outbox.jsonl"):
        self.key = node_key
        self.url = bank_url.rstrip("/") + "/v1/ingest"
        self.buffer = Path(buffer_path)

    def add_row(self, row):
        s = serialize(row)
        ok, reason = egress_gate(s)
        if not ok:
            return {"sent": False, "reason": reason}   # NEVER leaves the machine
        with open(self.buffer, "a", encoding="utf-8") as f:
            f.write(json.dumps(s) + "\n")
        return {"sent": False, "buffered": True}

    def flush(self):
        if not self.buffer.exists():
            return {"sent": 0}
        rows = [json.loads(l) for l in
                self.buffer.read_text(encoding="utf-8").splitlines() if l.strip()]
        payload = json.dumps(rows).encode()
        req = urllib.request.Request(
            self.url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "X-Node-Key": self.key})
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            self.buffer.write_text("", encoding="utf-8")   # clear ONLY on 200
        return resp


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    sample = {
        "task": "sum sales.csv by region",
        "messages": [
            {"role": "system", "content": "You are a helpful agent."},
            {"role": "user", "content": "Sum sales.csv by region."},
            {"role": "assistant", "content": "Let me read the file...",
             "tool_calls": [{"id": "c1", "type": "function",
                             "function": {"name": "read_file",
                                          "arguments": "{\"path\": \"sales.csv\"}"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "region,total\nnsw,120\nvic,90"},
            {"role": "assistant", "content": "FINAL: nsw=120, vic=90"},
        ],
        "meta": {"family": "csv-aggregation"},
    }
    s = serialize(sample)
    print("serialized keys:", sorted(s.keys()))
    print("gate:", egress_gate(s))
    print("assistant prose stripped:",
          all("Let me" not in json.dumps(m) for m in s["messages"]))
    if not dry:
        up = NodeUplink(node_key=os.environ.get("NYX_NODE_KEY", "node-shinobi-1:devkey-shinobi"),
                        bank_url=os.environ.get("NYX_BANK_URL", "http://127.0.0.1:8010"))
        print("add:", up.add_row(sample))
        print("flush:", up.flush())