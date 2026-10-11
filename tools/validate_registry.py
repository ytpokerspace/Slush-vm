#!/usr/bin/env python3
"""Validate SHUSHOS registry JSON using only Python's standard library."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB = ROOT / "registry" / "vocabulary.json"
CAPS = ROOT / "registry" / "capabilities.json"

def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("missing file: " + str(path.relative_to(ROOT))) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.relative_to(ROOT)}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc

def main():
    try:
        vocab = load(VOCAB)
        caps = load(CAPS)
    except ValueError as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1

    errors = []
    entries = vocab.get("entries", [])
    ids = [e.get("id") for e in entries]
    if any(not isinstance(x, str) or not x for x in ids):
        errors.append("every vocabulary entry needs a non-empty string id")
    if len(ids) != len(set(ids)):
        errors.append("duplicate vocabulary canonical IDs")

    aliases = {}
    for entry in entries:
        for field in ("symbol", "category", "meaning", "platform"):
            if not isinstance(entry.get(field), str) or not entry[field]:
                errors.append("{}: missing/invalid {}".format(entry.get("id", "<unknown>"), field))
        aliases.setdefault(entry.get("symbol"), []).append(entry.get("id"))

    contracts = caps.get("capabilities", [])
    cap_ids = [c.get("id") for c in contracts]
    if any(not isinstance(x, str) or not x for x in cap_ids):
        errors.append("every capability needs a non-empty string id")
    if len(cap_ids) != len(set(cap_ids)):
        errors.append("duplicate capability IDs")
    allowed = set(caps.get("status_values", []))
    required = ("version", "inputs", "outputs", "implementation", "permissions", "platforms", "status")
    for c in contracts:
        cid = c.get("id", "<unknown>")
        for field in required:
            if field not in c:
                errors.append("{}: missing {}".format(cid, field))
        if c.get("status") not in allowed:
            errors.append("{}: invalid status".format(cid))
        if c.get("status") == "tested" and c.get("tests", {}).get("status") not in ("passed", "passed_with_notes"):
            errors.append("{}: tested status requires passing tests".format(cid))
        if not isinstance(c.get("permissions"), list) or not c.get("permissions"):
            errors.append("{}: permissions must be a non-empty list".format(cid))
        if not isinstance(c.get("platforms"), list) or not c.get("platforms"):
            errors.append("{}: platforms must be a non-empty list".format(cid))
        if not isinstance(c.get("inputs"), dict) or not isinstance(c.get("outputs"), dict):
            errors.append("{}: inputs and outputs must be objects".format(cid))

    if errors:
        for error in errors:
            print("ERROR:", error, file=sys.stderr)
        return 1

    collisions = {symbol: ids for symbol, ids in aliases.items() if len(ids) > 1}
    print("OK: {} vocabulary entries; {} capability contracts.".format(len(ids), len(cap_ids)))
    if collisions:
        print("NOTICE: {} reused emoji aliases; resolver must disambiguate by namespace/context.".format(len(collisions)))
        for symbol, targets in sorted(collisions.items()):
            print("  {}: {}".format(symbol, ", ".join(targets)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
