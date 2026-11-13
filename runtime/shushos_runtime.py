"""SHUSHOS host capability runtime.

This is a deterministic host-side capability layer and MCP stdio server.
It is not the missing SHUSH parser/full VM. Capabilities are pure or
data-in/data-out; no shell, network, or arbitrary code execution is exposed.
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import json
import sys
from collections import deque
from typing import Any

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "shushos-capability-runtime", "version": "0.1.0"}


class CapabilityError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise CapabilityError("E_INPUT_TYPE", f"{name} must be an object")
    return value


def _string(value: Any, name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise CapabilityError("E_INPUT_TYPE", f"{name} must be a non-empty string")
    return value


def _integer(value: Any, name: str, minimum: int = 0, maximum: int = 10_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise CapabilityError("E_INPUT_RANGE", f"{name} must be an integer in {minimum}..{maximum}")
    return value


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: Any, name: str) -> bytes:
    _string(value, name)
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise CapabilityError("E_ENCODING", f"{name} is not valid base64") from exc


def _tags(value: Any) -> set[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise CapabilityError("E_INPUT_TYPE", "tags must be a list of strings")
    return {x.strip().casefold() for x in value if x.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# ARC-2: adapter to the authoritative primitive-first solver package.
# The solver is not copied here. Install/checkout arc_r2 and expose it on
# PYTHONPATH; this adapter calls arc_r2.primitives.fit_program directly.
# ---------------------------------------------------------------------------

def arc2_fit_program(args: dict) -> dict:
    args = _object(args, "arguments")
    examples = args.get("training_pairs")
    if not isinstance(examples, list) or not examples:
        raise CapabilityError("E_INPUT_TYPE", "training_pairs must be a non-empty list")
    normalized = []
    for index, pair in enumerate(examples):
        pair = _object(pair, f"training_pairs[{index}]")
        if "input" not in pair or "output" not in pair:
            raise CapabilityError("E_INPUT_TYPE", f"training_pairs[{index}] requires input and output")
        normalized.append((pair["input"], pair["output"]))
    candidate_cap = _integer(args.get("candidate_cap", 5000), "candidate_cap", 1, 50000)
    max_depth = _integer(args.get("max_depth", 2), "max_depth", 0, 2)
    try:
        module = importlib.import_module("arc_r2.primitives")
    except ImportError as exc:
        raise CapabilityError(
            "E_DEPENDENCY_MISSING",
            "ARC-2 package arc_r2 is not installed or not on PYTHONPATH; see docs/LLM_INTEGRATION.md",
        ) from exc
    try:
        pairs = tuple((module.as_grid(source), module.as_grid(target)) for source, target in normalized)
        result = module.fit_program(pairs, candidate_cap=candidate_cap, max_depth=max_depth)
    except (ValueError, TypeError, IndexError) as exc:
        raise CapabilityError("E_ARC2_INPUT", str(exc)) from exc
    program = result.program
    operations = []
    if program is not None:
        operations = [{"name": op.name, "args": list(op.args)} for op in program.operations]
    return {
        "capability": "arc2.fit_program",
        "solver": "arc_r2.primitives.fit_program",
        "search": "deterministic primitive enumeration",
        "mcts_used": False,
        "beam_search_used": False,
        "training_pair_count": len(pairs),
        "candidate_cap": candidate_cap,
        "max_depth": max_depth,
        "candidates_evaluated": result.candidates_evaluated,
        "exact_fit": bool(result.exact_fit),
        "fit_program_count": result.fit_program_count,
        "program": operations if result.exact_fit else None,
        "program_text": str(program) if result.exact_fit and program is not None else None,
        "acceptance": "all supplied training pairs must match exactly",
        "generalization_claim": False,
        "official_benchmark_score": None,
    }


# ---------------------------------------------------------------------------
# ARC-AGI-3: validated action envelope only.
# No game policy or transition model is specified in the source notes, so
# this capability checks an LLM-proposed action against the environment's
# explicit legal-action list. It does not play the game or call an API.
# ---------------------------------------------------------------------------

def arc3_validate_action(args: dict) -> dict:
    args = _object(args, "arguments")
    game_id = _string(args.get("game_id"), "game_id")
    turn_id = _string(args.get("turn_id"), "turn_id")
    state_digest = _string(args.get("state_digest"), "state_digest")
    available = args.get("available_actions")
    if not isinstance(available, list) or not available:
        raise CapabilityError("E_INPUT_TYPE", "available_actions must be a non-empty list")
    if any(not isinstance(item, (str, int, dict, list)) for item in available):
        raise CapabilityError("E_INPUT_TYPE", "available_actions must contain JSON values")
    proposed = args.get("proposed_action")
    if proposed not in available:
        raise CapabilityError("E_ACTION_NOT_ALLOWED", "proposed_action is not in available_actions")
    return {
        "capability": "arc3.validate_action",
        "game_id": game_id,
        "turn_id": turn_id,
        "state_digest": state_digest,
        "action": proposed,
        "valid": True,
        "policy_status": "externally_proposed",
        "environment_executed": False,
        "note": "Legality envelope only; no ARC-AGI-3 game policy or transition model is implemented.",
    }


# ---------------------------------------------------------------------------
# QBS: structured multi-criteria evaluation. No fake aggregate probability.
# Pareto fronts retain separate dimensions rather than inventing weights.
# ---------------------------------------------------------------------------

_QBS_MAX = ("probability", "feasibility", "reasonability", "expected_success")
_QBS_MIN = ("cost", "risk")


def qbs_rank_hypotheses(args: dict) -> dict:
    args = _object(args, "arguments")
    hypotheses = args.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        raise CapabilityError("E_INPUT_TYPE", "hypotheses must be a non-empty list")
    prepared = []
    seen = set()
    for index, raw in enumerate(hypotheses):
        item = _object(raw, f"hypotheses[{index}]")
        hid = _string(item.get("id"), f"hypotheses[{index}].id")
        if hid in seen:
            raise CapabilityError("E_DUPLICATE_ID", f"duplicate hypothesis id: {hid}")
        seen.add(hid)
        hard_ok = item.get("hard_constraints_met", True)
        if not isinstance(hard_ok, bool):
            raise CapabilityError("E_INPUT_TYPE", f"{hid}.hard_constraints_met must be boolean")
        values = {}
        for key in _QBS_MAX + _QBS_MIN:
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CapabilityError("E_INPUT_TYPE", f"{hid}.{key} must be numeric")
            if value < 0 or value > 1:
                raise CapabilityError("E_INPUT_RANGE", f"{hid}.{key} must be in 0..1")
            values[key] = float(value)
        prepared.append({
            "id": hid,
            "hard_constraints_met": hard_ok,
            "metrics": values,
            "evidence_for": item.get("evidence_for", []),
            "evidence_against": item.get("evidence_against", []),
            "assumptions": item.get("assumptions", []),
        })
    eligible = [x for x in prepared if x["hard_constraints_met"]]
    def dominates(a: dict, b: dict) -> bool:
        av, bv = a["metrics"], b["metrics"]
        no_worse = all(av[k] >= bv[k] for k in _QBS_MAX) and all(av[k] <= bv[k] for k in _QBS_MIN)
        strictly_better = any(av[k] > bv[k] for k in _QBS_MAX) or any(av[k] < bv[k] for k in _QBS_MIN)
        return no_worse and strictly_better
    remaining = list(eligible)
    fronts = []
    rank = 1
    while remaining:
        front = [x for x in remaining if not any(dominates(other, x) for other in remaining if other is not x)]
        front.sort(key=lambda x: x["id"])
        fronts.append({"pareto_front": rank, "hypotheses": front})
        selected = {x["id"] for x in front}
        remaining = [x for x in remaining if x["id"] not in selected]
        rank += 1
    excluded = [{"id": x["id"], "reason": "hard_constraints_not_met"} for x in prepared if not x["hard_constraints_met"]]
    return {
        "capability": "qbs.rank_hypotheses",
        "method": "non-dominated Pareto fronts",
        "dimensions_kept_separate": list(_QBS_MAX + _QBS_MIN),
        "aggregate_score": None,
        "probabilities_calibrated": False,
        "fronts": fronts,
        "excluded": excluded,
        "interpretation": "Pareto rank is a comparison aid, not a calibrated probability or proof of correctness.",
    }


# ---------------------------------------------------------------------------
# Glyphic Path Memory: versioned events, exact evidence hash, tag retrieval,
# and suffix/prefix stitching. Hybrid paths remain hypotheses.
# ---------------------------------------------------------------------------

def glyphic_create_path(args: dict) -> dict:
    args = _object(args, "arguments")
    path_id = _string(args.get("path_id"), "path_id")
    records = args.get("records", [])
    if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
        raise CapabilityError("E_INPUT_TYPE", "records must be a list of path objects")
    if any(x.get("path_id") == path_id for x in records):
        raise CapabilityError("E_DUPLICATE_ID", f"path_id already exists: {path_id}")
    codebook_version = _string(args.get("codebook_version", "1.0.0"), "codebook_version")
    codebook = _object(args.get("codebook", {}), "codebook")
    events = args.get("events")
    if not isinstance(events, list) or not events:
        raise CapabilityError("E_INPUT_TYPE", "events must be a non-empty list")
    encoded_events = []
    for index, raw in enumerate(events):
        event = _object(raw, f"events[{index}]")
        event_type = _string(event.get("type"), f"events[{index}].type")
        glyph = event.get("glyph", codebook.get(event_type))
        if glyph is None:
            raise CapabilityError("E_CODEBOOK_MISS", f"no glyph mapping for event type {event_type}")
        encoded_events.append({"type": event_type, "glyph": _string(glyph, f"events[{index}].glyph")})
    evidence = args.get("evidence", "")
    if not isinstance(evidence, str):
        raise CapabilityError("E_INPUT_TYPE", "evidence must be a string")
    evidence_bytes = evidence.encode("utf-8")
    status = args.get("status", "hypothesis")
    if status not in ("hypothesis", "tested", "verified", "rejected"):
        raise CapabilityError("E_INPUT_VALUE", "status must be hypothesis, tested, verified, or rejected")
    record = {
        "path_id": path_id,
        "codebook_version": codebook_version,
        "events": encoded_events,
        "glyph_sequence": [x["glyph"] for x in encoded_events],
        "tags": sorted(_tags(args.get("tags", []))),
        "status": status,
        "evidence_b64": _b64(evidence_bytes),
        "evidence_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "provenance": [path_id],
    }
    return {"capability": "glyphic.create_path", "record": record, "records": records + [record]}


def glyphic_verify_path(record: dict) -> dict:
    record = _object(record, "record")
    evidence = _unb64(record.get("evidence_b64", ""), "evidence_b64")
    actual = hashlib.sha256(evidence).hexdigest()
    expected = _string(record.get("evidence_sha256"), "evidence_sha256")
    return {"valid": actual == expected, "expected_sha256": expected, "actual_sha256": actual,
            "evidence_utf8": evidence.decode("utf-8", errors="strict") if actual == expected else None}


def glyphic_retrieve_paths(args: dict) -> dict:
    args = _object(args, "arguments")
    records = args.get("records")
    if not isinstance(records, list):
        raise CapabilityError("E_INPUT_TYPE", "records must be a list")
    query_tags = _tags(args.get("query_tags", []))
    limit = _integer(args.get("limit", 10), "limit", 1, 1000)
    matches = []
    for record in records:
        record = _object(record, "record")
        similarity = _jaccard(query_tags, _tags(record.get("tags", [])))
        if similarity > 0:
            matches.append({"record": record, "tag_similarity": similarity})
    matches.sort(key=lambda x: (-x["tag_similarity"], x["record"].get("path_id", "")))
    return {"capability": "glyphic.retrieve_paths", "method": "tag Jaccard overlap",
            "semantic_embedding_used": False, "matches": matches[:limit]}


def glyphic_hybridize_paths(args: dict) -> dict:
    args = _object(args, "arguments")
    left = _object(args.get("left"), "left")
    right = _object(args.get("right"), "right")
    a, b = left.get("events"), right.get("events")
    if not isinstance(a, list) or not isinstance(b, list) or not a or not b:
        raise CapabilityError("E_INPUT_TYPE", "left and right require non-empty events")
    if left.get("codebook_version") != right.get("codebook_version"):
        raise CapabilityError("E_CODEBOOK_VERSION", "cannot stitch different codebook versions")
    overlap = 0
    for size in range(1, min(len(a), len(b)) + 1):
        if a[-size:] == b[:size]:
            overlap = size
    events = a + b[overlap:]
    provenance = list(dict.fromkeys(left.get("provenance", [left.get("path_id")]) +
                                    right.get("provenance", [right.get("path_id")])))
    return {
        "capability": "glyphic.hybridize_paths",
        "record": {
            "path_id": _string(args.get("new_path_id"), "new_path_id"),
            "codebook_version": left["codebook_version"],
            "events": events,
            "glyph_sequence": [x["glyph"] for x in events],
            "tags": sorted(_tags(left.get("tags", [])) | _tags(right.get("tags", []))),
            "status": "hypothesis",
            "evidence_sources": provenance,
            "overlap_events": overlap,
            "evidence_b64": None,
            "evidence_sha256": None,
        },
        "verified": False,
        "note": "Suffix/prefix stitching is structural only; it does not prove semantic compatibility.",
    }


# ---------------------------------------------------------------------------
# CSC-LCH: source bytes remain authoritative; graph nodes are indexed views.
# Hydration is byte-range based and always verifies the full source digest.
# ---------------------------------------------------------------------------

_TIERS = {"T1": 0.90, "T2": 0.75, "T3": 0.40, "T4": 0.08, "Archive": 0.02}


def csc_lch_ingest(args: dict) -> dict:
    args = _object(args, "arguments")
    source_id = _string(args.get("source_id"), "source_id")
    records = args.get("records", [])
    if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
        raise CapabilityError("E_INPUT_TYPE", "records must be a list")
    if any(x.get("source_id") == source_id for x in records):
        raise CapabilityError("E_DUPLICATE_ID", f"source_id already exists: {source_id}")
    source_b64 = args.get("source_b64")
    if source_b64 is None:
        source_text = args.get("source_text")
        if not isinstance(source_text, str):
            raise CapabilityError("E_INPUT_TYPE", "provide source_text or source_b64")
        source_bytes = source_text.encode("utf-8")
    else:
        source_bytes = _unb64(source_b64, "source_b64")
    nodes = args.get("nodes", [])
    if not isinstance(nodes, list):
        raise CapabilityError("E_INPUT_TYPE", "nodes must be a list")
    node_ids = set()
    checked_nodes = []
    for index, raw in enumerate(nodes):
        node = _object(raw, f"nodes[{index}]")
        nid = _string(node.get("id"), f"nodes[{index}].id")
        if nid in node_ids:
            raise CapabilityError("E_DUPLICATE_ID", f"duplicate node id: {nid}")
        node_ids.add(nid)
        start = _integer(node.get("start", 0), f"{nid}.start", 0, len(source_bytes))
        end = _integer(node.get("end", len(source_bytes)), f"{nid}.end", 0, len(source_bytes))
        if end < start:
            raise CapabilityError("E_INPUT_RANGE", f"{nid}.end must be >= start")
        tier = node.get("tier", "T3")
        if tier not in _TIERS:
            raise CapabilityError("E_INPUT_VALUE", f"unknown tier: {tier}")
        checked_nodes.append({"id": nid, "tags": sorted(_tags(node.get("tags", []))),
                              "tier": tier, "start": start, "end": end,
                              "neighbors": list(node.get("neighbors", []))})
    for node in checked_nodes:
        if any(n not in node_ids for n in node["neighbors"]):
            raise CapabilityError("E_GRAPH_REFERENCE", f"node {node['id']} references unknown neighbor")
    record = {
        "source_id": source_id,
        "source_b64": _b64(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "nodes": checked_nodes,
    }
    return {"capability": "csc_lch.ingest", "record": record, "records": records + [record]}


def csc_lch_compress(args: dict) -> dict:
    args = _object(args, "arguments")
    record = _object(args.get("record"), "record")
    threshold = args.get("retain_weight_at_least", 0.40)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        raise CapabilityError("E_INPUT_RANGE", "retain_weight_at_least must be in 0..1")
    active, stubs = [], []
    for node in record.get("nodes", []):
        item = {"source_id": record["source_id"], **node}
        if _TIERS[node["tier"]] >= threshold:
            active.append(item)
        else:
            stubs.append({"source_id": record["source_id"], "node_id": node["id"],
                          "tier": node["tier"], "tags": node["tags"], "source_sha256": record["source_sha256"]})
    graph_bytes = len(_json_bytes(record.get("nodes", [])))
    source_bytes = record["source_bytes"]
    active_bytes = len(_json_bytes(active))
    return {
        "capability": "csc_lch.compress",
        "source_preserved": True,
        "source_sha256": record["source_sha256"],
        "active_nodes": active,
        "stubs": stubs,
        "source_bytes": source_bytes,
        "graph_bytes": graph_bytes,
        "total_bytes": source_bytes + graph_bytes,
        "active_representation_bytes": active_bytes,
        "active_context_reduction_bytes": max(0, graph_bytes - active_bytes),
        "tier_weights_are_configuration": True,
        "note": "Active representation reduction is not total-storage reduction; original source bytes remain stored.",
    }


def csc_lch_hydrate(args: dict) -> dict:
    args = _object(args, "arguments")
    record = _object(args.get("record"), "record")
    source = _unb64(record.get("source_b64", ""), "source_b64")
    actual_hash = hashlib.sha256(source).hexdigest()
    if actual_hash != record.get("source_sha256"):
        raise CapabilityError("E_INTEGRITY_FAILURE", "source SHA-256 verification failed")
    nodes = record.get("nodes", [])
    by_id = {node["id"]: node for node in nodes}
    query = _tags(args.get("query_tags", []))
    budget = _integer(args.get("budget_bytes", len(source)), "budget_bytes", 0, 100_000_000)
    max_hops = _integer(args.get("max_hops", 1), "max_hops", 0, 100)
    seeds = sorted((node for node in nodes if _jaccard(query, _tags(node.get("tags", []))) > 0),
                   key=lambda n: (-_jaccard(query, _tags(n.get("tags", []))), n["id"]))
    queue = deque((node["id"], 0) for node in seeds)
    visited = set()
    selected = []
    while queue:
        nid, depth = queue.popleft()
        if nid in visited or nid not in by_id:
            continue
        visited.add(nid)
        selected.append(by_id[nid])
        if depth < max_hops:
            for neighbor in sorted(by_id[nid].get("neighbors", [])):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))
    ranges = sorted((n["start"], n["end"], n["id"]) for n in selected)
    merged = []
    for start, end, nid in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
            merged[-1][2].append(nid)
        else:
            merged.append([start, end, [nid]])
    hydrated, used = [], 0
    for start, end, node_ids in merged:
        size = end - start
        if used + size > budget:
            continue
        piece = source[start:end]
        hydrated.append({"start": start, "end": end, "node_ids": node_ids, "bytes_b64": _b64(piece)})
        used += size
    return {
        "capability": "csc_lch.hydrate",
        "source_integrity_verified": True,
        "source_sha256": actual_hash,
        "selected_node_ids": [n["id"] for n in selected],
        "hydrated_ranges": hydrated,
        "hydrated_bytes": used,
        "budget_bytes": budget,
        "max_hops": max_hops,
    }


def csc_lch_reconstruct(args: dict) -> dict:
    args = _object(args, "arguments")
    record = _object(args.get("record"), "record")
    source = _unb64(record.get("source_b64", ""), "source_b64")
    digest = hashlib.sha256(source).hexdigest()
    if digest != record.get("source_sha256"):
        raise CapabilityError("E_INTEGRITY_FAILURE", "source SHA-256 verification failed")
    return {"capability": "csc_lch.reconstruct", "source_id": record["source_id"],
            "source_b64": _b64(source), "source_bytes": len(source),
            "source_sha256": digest, "exact_reconstruction": True}


# ---------------------------------------------------------------------------
# LLM-facing MCP tools. Tool schemas are explicit and every call routes to a
# fixed capability; model-provided strings are never evaluated as code.
# ---------------------------------------------------------------------------

TOOLS = [
    {"name": "arc2_fit_program", "description": "Fit the installed ARC-2 primitive-first solver to supplied training pairs. Returns a candidate only when every supplied pair matches exactly. Does not run an official benchmark or use test answers.",
     "inputSchema": {"type": "object", "properties": {"training_pairs": {"type": "array", "items": {"type": "object", "properties": {"input": {"type": "array"}, "output": {"type": "array"}}, "required": ["input", "output"]}}, "candidate_cap": {"type": "integer", "minimum": 1, "maximum": 50000}, "max_depth": {"type": "integer", "minimum": 0, "maximum": 2}}, "required": ["training_pairs"], "additionalProperties": False}},
    {"name": "arc3_validate_action", "description": "Check that an externally proposed ARC-AGI-3 action is in the environment-provided legal action list. Does not execute the action or implement a game policy.",
     "inputSchema": {"type": "object", "properties": {"game_id": {"type": "string"}, "turn_id": {"type": "string"}, "state_digest": {"type": "string"}, "available_actions": {"type": "array"}, "proposed_action": {}}, "required": ["game_id", "turn_id", "state_digest", "available_actions", "proposed_action"], "additionalProperties": False}},
    {"name": "qbs_rank_hypotheses", "description": "Compare hypotheses with separate criteria using Pareto fronts; does not invent an aggregate score or calibrated probabilities.",
     "inputSchema": {"type": "object", "properties": {"hypotheses": {"type": "array", "items": {"type": "object"}}}, "required": ["hypotheses"], "additionalProperties": False}},
    {"name": "glyphic_create_path", "description": "Create a versioned glyphic event path with tags and SHA-256-protected evidence. Duplicate path IDs are rejected.",
     "inputSchema": {"type": "object", "properties": {"path_id": {"type": "string"}, "records": {"type": "array"}, "codebook_version": {"type": "string"}, "codebook": {"type": "object"}, "events": {"type": "array"}, "tags": {"type": "array", "items": {"type": "string"}}, "status": {"type": "string"}, "evidence": {"type": "string"}}, "required": ["path_id", "events"], "additionalProperties": False}},
    {"name": "glyphic_retrieve_paths", "description": "Retrieve glyphic paths by tag Jaccard overlap. This is not embedding-based semantic search.",
     "inputSchema": {"type": "object", "properties": {"records": {"type": "array"}, "query_tags": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer", "minimum": 1, "maximum": 1000}}, "required": ["records", "query_tags"], "additionalProperties": False}},
    {"name": "glyphic_hybridize_paths", "description": "Stitch paths at their maximal suffix/prefix event overlap. The result is always labelled a hypothesis.",
     "inputSchema": {"type": "object", "properties": {"left": {"type": "object"}, "right": {"type": "object"}, "new_path_id": {"type": "string"}}, "required": ["left", "right", "new_path_id"], "additionalProperties": False}},
    {"name": "csc_lch_ingest", "description": "Store exact source bytes with SHA-256 and optional graph nodes. Duplicate source IDs are rejected.",
     "inputSchema": {"type": "object", "properties": {"source_id": {"type": "string"}, "records": {"type": "array"}, "source_text": {"type": "string"}, "source_b64": {"type": "string"}, "nodes": {"type": "array"}}, "required": ["source_id"], "additionalProperties": False}},
    {"name": "csc_lch_compress", "description": "Create active node views and lazy stubs without deleting original source evidence. Reports source, graph, total and active bytes separately.",
     "inputSchema": {"type": "object", "properties": {"record": {"type": "object"}, "retain_weight_at_least": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["record"], "additionalProperties": False}},
    {"name": "csc_lch_hydrate", "description": "Hydrate relevant source byte ranges within a byte budget and graph-hop limit, after verifying the source SHA-256.",
     "inputSchema": {"type": "object", "properties": {"record": {"type": "object"}, "query_tags": {"type": "array", "items": {"type": "string"}}, "budget_bytes": {"type": "integer", "minimum": 0}, "max_hops": {"type": "integer", "minimum": 0}}, "required": ["record", "query_tags"], "additionalProperties": False}},
    {"name": "csc_lch_reconstruct", "description": "Reconstruct the exact original source bytes after SHA-256 verification.",
     "inputSchema": {"type": "object", "properties": {"record": {"type": "object"}}, "required": ["record"], "additionalProperties": False}},
]


def call_tool(name: str, arguments: dict) -> dict:
    dispatch = {
        "arc2_fit_program": arc2_fit_program,
        "arc3_validate_action": arc3_validate_action,
        "qbs_rank_hypotheses": qbs_rank_hypotheses,
        "glyphic_create_path": glyphic_create_path,
        "glyphic_retrieve_paths": glyphic_retrieve_paths,
        "glyphic_hybridize_paths": glyphic_hybridize_paths,
        "csc_lch_ingest": csc_lch_ingest,
        "csc_lch_compress": csc_lch_compress,
        "csc_lch_hydrate": csc_lch_hydrate,
        "csc_lch_reconstruct": csc_lch_reconstruct,
    }
    if name not in dispatch:
        raise CapabilityError("E_TOOL_NOT_FOUND", f"unknown tool: {name}")
    return dispatch[name](arguments)


def _reply(message: dict) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        params = message.get("params", {})
        requested = params.get("protocolVersion", PROTOCOL_VERSION)
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": requested, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params", {})
        try:
            result = call_tool(params.get("name", ""), params.get("arguments", {}))
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": False,
            }}
        except CapabilityError as exc:
            payload = {"error": exc.as_dict()}
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
                "isError": True,
            }}
        except Exception as exc:  # defensive boundary: never crash the stdio loop
            payload = {"error": {"code": "E_INTERNAL", "message": f"{type(exc).__name__}: {exc}"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
                "isError": True,
            }}
    if request_id is not None:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    return None


def serve_stdio() -> None:
    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = _reply(message)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {exc}"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve_stdio()
