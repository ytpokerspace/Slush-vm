"""Emoji Glyph Protocol (EGP): typed DSL for ARC-AGI-3 solver instructions.

Emoji are stable surface tokens; operation identifiers and structured arguments
are the executable semantics. The renderer is dynamic, but execution is explicit:
no environment side effects occur unless a caller registers a handler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Callable

# Keep old glyphs stable. New glyphs extend the protocol without changing aliases.
GLYPHS: dict[str, str] = {
    "👁️": "observe",
    "🔍": "segment",
    "🧩": "relate",
    "📐": "geometry",
    "🧭": "orient",
    "↔️": "track",
    "⚙️": "physics",
    "🧱": "beam",
    "🌳": "mcts",
    "⚡": "parallel",
    "🔦": "attend",
    "🧠": "hypothesize",
    "🔮": "predict",
    "📊": "probability",
    "🏆": "reward",
    "⛔": "risk",
    "🧮": "value",
    "🧪": "probe",
    "🎯": "select",
    "▶️": "act",
    "✔️": "verify",
    "💾": "memorize",
    "🔐": "checksum",
    "📦": "compress",
    "🗃️": "memory",
    "🧬": "learn",
    "🔁": "replan",
    "↩️": "undo",
}

OPERATION_GLYPHS = {operation: glyph for glyph, operation in GLYPHS.items()}
ACTION_OPERATIONS = {"act", "undo"}
DEFAULTS: dict[str, Any] = {
    "orient": {"coordinate_system": "infer", "allow_rotation": True, "allow_reflection": True},
    "physics": {"model": "evidence_gated", "infer_only_from_observations": True},
    "beam": {"width": 12, "horizon": 4, "deduplicate_states": True},
    "mcts": {"depth": 2, "simulations": 32, "exploration": 1.2},
    "parallel": {"mode": "root", "workers": "auto"},
    "attend": {"focus": ["player", "goals", "hazards", "unknowns"]},
    "probability": {"calibration": "empirical", "separate_by_context": True},
    "reward": {"win_priority": "absolute", "bonus": "verified_only"},
    "risk": {"unknown_is_not_safe": True},
    "value": {"minimize_actions": True},
    "memory": {"event_chunk": 4, "chunks_per_rollup": 4, "persist": True},
    "checksum": {"algorithm": "sha256", "canonicalization": "json_sorted_compact"},
    "compress": {"retain_structured_source": True, "glyphs_are_lossless": False},
    "learn": {"source": "verified_observed_transitions"},
    "replan": {"after_every_observation": True},
}

@dataclass(frozen=True)
class Instruction:
    operation: str
    argument: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]

class DSLParseError(ValueError):
    pass

def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
        return float(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [part.strip().strip("'\\\"") for part in value[1:-1].split(",") if part.strip()]
    return value

def _parse_arguments(raw: str) -> tuple[str, dict[str, Any]]:
    raw = raw.strip()
    if not raw:
        return "", {}
    if "=" not in raw:
        return raw, {}
    params: dict[str, Any] = {}
    positional: list[str] = []
    for part in re.split(r",(?=(?:[^'\"]|'[^']*'|\"[^\"]*\")*$)", raw):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key):
                raise DSLParseError(f"invalid parameter name: {key}")
            params[key] = _parse_scalar(value)
        else:
            positional.append(part)
    return ",".join(positional), params

def parse_program(source: str) -> Program:
    instructions: list[Instruction] = []
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line in {"ARC3 {", "EGP {", "}"}:
            continue
        glyph = next((item for item in sorted(GLYPHS, key=len, reverse=True) if line.startswith(item)), None)
        if glyph is None:
            raise DSLParseError(f"line {line_number}: unknown or missing glyph")
        operation = GLYPHS[glyph]
        remainder = line[len(glyph):].strip()
        if remainder.startswith(operation.upper()):
            remainder = remainder[len(operation):].strip()
        if remainder.startswith("("):
            if not remainder.endswith(")"):
                raise DSLParseError(f"line {line_number}: unclosed argument list")
            remainder = remainder[1:-1].strip()
        elif remainder:
            raise DSLParseError(f"line {line_number}: expected operation arguments in parentheses")
        argument, parameters = _parse_arguments(remainder)
        instructions.append(Instruction(operation, argument or "context", parameters))
    if not instructions:
        raise DSLParseError("program contains no instructions")
    return Program(tuple(instructions))

def validate_program(program: Program) -> None:
    seen_observe = False
    seen_select = False
    seen_act = False
    seen_verify = False
    for index, item in enumerate(program.instructions):
        if item.operation not in OPERATION_GLYPHS:
            raise DSLParseError(f"instruction {index}: unsupported operation {item.operation}")
        if item.operation == "observe":
            seen_observe = True
        elif not seen_observe:
            raise DSLParseError(f"instruction {index}: observe must precede reasoning")
        if item.operation == "select":
            seen_select = True
        if item.operation in ACTION_OPERATIONS and not seen_select:
            raise DSLParseError(f"instruction {index}: select must precede action")
        if item.operation in ACTION_OPERATIONS:
            seen_act = True
        if item.operation == "verify":
            if not seen_act:
                raise DSLParseError(f"instruction {index}: verify must follow an action")
            seen_verify = True
        if item.operation == "memorize" and seen_act and not seen_verify:
            raise DSLParseError(f"instruction {index}: observed action must be verified before memorizing")

def compile_program(program: Program) -> list[dict[str, Any]]:
    """Resolve defaults and emit a typed, serializable execution plan."""
    validate_program(program)
    compiled = []
    for index, item in enumerate(program.instructions):
        parameters = dict(DEFAULTS.get(item.operation, {}))
        parameters.update(item.parameters)
        compiled.append({
            "index": index,
            "glyph": OPERATION_GLYPHS[item.operation],
            "operation": item.operation,
            "argument": item.argument,
            "parameters": parameters,
            "side_effect": item.operation in ACTION_OPERATIONS,
        })
    return compiled

def execute_program(program: Program,
                    handlers: dict[str, Callable[[str, dict[str, Any]], Any]],
                    context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run registered local handlers; ACT/UNDO require explicit handlers."""
    compiled = compile_program(program)
    state = dict(context or {})
    trace = []
    for item in compiled:
        operation = item["operation"]
        handler = handlers.get(operation)
        if handler is None:
            trace.append({"operation": operation, "status": "skipped_no_handler"})
            continue
        state[operation] = handler(item["argument"], {**state, "parameters": item["parameters"]})
        trace.append({"operation": operation, "status": "executed"})
    return {"state": state, "trace": trace, "instruction_count": len(compiled)}

def render_protocol(context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render a compact, context-sensitive protocol view for diagnostics/UI."""
    ctx = dict(context or {})
    stages = [
        ("👁️", "observe", {"frame_id": ctx.get("frame_id"), "grid_shape": ctx.get("grid_shape")}),
        ("🔍", "segment", {"object_count": ctx.get("object_count")}),
        ("🧭", "orient", {"orientation": ctx.get("orientation", "unknown")}),
        ("↔️", "track", {"tracked_objects": ctx.get("tracked_objects")}),
        ("⚙️", "physics", {"motion_model": ctx.get("motion_model", "evidence_gated")}),
        ("🔦", "attend", {"focus": ctx.get("attention_focus", ["player", "goals", "hazards"])}),
        ("📊", "probability", {"success_estimates": ctx.get("success_estimates", "uncalibrated")}),
        ("🏆", "reward", {"verified_rewards": ctx.get("verified_rewards", [])}),
        ("⛔", "risk", {"risk_flags": ctx.get("risk_flags", [])}),
        ("🧱", "beam", {"width": ctx.get("beam_width", 12), "horizon": ctx.get("beam_horizon", 4)}),
        ("🌳", "mcts", {"depth": ctx.get("mcts_depth", 2), "simulations": ctx.get("mcts_simulations", 32)}),
        ("⚡", "parallel", {"mode": ctx.get("parallel_mode", "root")}),
        ("🎯", "select", {"legal_action_count": ctx.get("legal_action_count")}),
        ("▶️", "act", {"selected_action": ctx.get("selected_action")}),
        ("✔️", "verify", {"outcome": ctx.get("outcome", "pending")}),
        ("💾", "memorize", {"memory_glyph": ctx.get("memory_glyph")}),
        ("🔐", "checksum", {"scene_checksum": ctx.get("scene_checksum")}),
        ("📦", "compress", {"chunk_size": ctx.get("memory_chunk_size", 4)}),
        ("🔁", "replan", {"enabled": True}),
    ]
    rendered = []
    for glyph, operation, fields in stages:
        visible = {key: value for key, value in fields.items() if value is not None}
        rendered.append({"glyph": glyph, "operation": operation, "fields": visible})
    canonical = json.dumps(rendered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "protocol": "EGP-ARC3/1.0",
        "glyph_stream": " ".join(item["glyph"] for item in rendered),
        "stages": rendered,
        "context_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "semantics": "typed operations and structured fields; glyph stream is a compact rendering",
    }

DEFAULT_PROGRAM = """EGP {
👁️ OBSERVE(frame)
🔍 SEGMENT(objects)
🧩 RELATE(objects)
📐 GEOMETRY(objects)
🧭 ORIENT(grid, coordinate_system=infer)
↔️ TRACK(objects)
⚙️ PHYSICS(model=evidence_gated)
🔦 ATTEND(player,goals,hazards,unknowns)
🧠 HYPOTHESIZE(mechanics)
🔮 PREDICT(legal_actions)
📊 PROBABILITY(calibration=empirical)
🏆 REWARD(bonus=verified_only,win_priority=absolute)
⛔ RISK(unknown_is_not_safe=true)
🧮 VALUE(minimize_actions=true)
🧪 PROBE(information_gain)
🧱 BEAM(width=12,horizon=4)
🌳 MCTS(depth=2,simulations=32)
⚡ PARALLEL(mode=root,workers=auto)
🎯 SELECT(best_legal_action)
▶️ ACT(best_legal_action)
✔️ VERIFY(actual_observation)
💾 MEMORIZE(verified_transition)
🔐 CHECKSUM(algorithm=sha256)
📦 COMPRESS(event_chunk=4,chunks_per_rollup=4)
🗃️ MEMORY(persist=true)
🧬 LEARN(verified_observed_transitions)
🔁 REPLAN(after_every_observation=true)
}"""
