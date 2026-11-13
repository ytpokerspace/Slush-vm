"""Typed emoji-native surface DSL for ARC-AGI-3 reasoning."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable

GLYPHS = {
    "👁️": "observe", "🔍": "segment", "🧩": "relate", "📐": "geometry",
    "↔️": "track", "🧠": "hypothesize", "🔮": "predict", "🧪": "probe",
    "🌳": "search", "🎯": "select", "▶️": "act", "↩️": "undo",
    "✔️": "verify", "💾": "memorize",
}

@dataclass(frozen=True)
class Instruction:
    operation: str
    argument: str = ""

@dataclass(frozen=True)
class Program:
    instructions: tuple[Instruction, ...]

class DSLParseError(ValueError):
    pass

def parse_program(source: str) -> Program:
    instructions = []
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line in {"ARC3 {", "}"}:
            continue
        glyph = next((item for item in GLYPHS if line.startswith(item)), None)
        if glyph is None:
            raise DSLParseError(f"line {line_number}: unknown or missing glyph")
        operation = GLYPHS[glyph]
        remainder = line[len(glyph):].strip()
        if remainder.startswith(operation.upper()):
            remainder = remainder[len(operation):].strip()
        if remainder.startswith("(") and remainder.endswith(")"):
            remainder = remainder[1:-1].strip()
        if not remainder:
            remainder = "context"
        instructions.append(Instruction(operation, remainder))
    if not instructions:
        raise DSLParseError("program contains no instructions")
    return Program(tuple(instructions))

def validate_program(program: Program) -> None:
    seen_observe = False
    seen_select = False
    for index, item in enumerate(program.instructions):
        if item.operation not in set(GLYPHS.values()):
            raise DSLParseError(f"instruction {index}: unsupported operation")
        if item.operation == "observe":
            seen_observe = True
        elif not seen_observe:
            raise DSLParseError(f"instruction {index}: observe must precede reasoning")
        if item.operation == "select":
            seen_select = True
        if item.operation == "act" and not seen_select:
            raise DSLParseError(f"instruction {index}: select must precede act")

def execute_program(program: Program,
                    handlers: dict[str, Callable[[str, dict[str, Any]], Any]],
                    context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run registered local handlers; ACT/UNDO require explicit handlers."""
    validate_program(program)
    state = dict(context or {})
    trace = []
    for item in program.instructions:
        handler = handlers.get(item.operation)
        if handler is None:
            trace.append({"operation": item.operation, "status": "skipped_no_handler"})
            continue
        state[item.operation] = handler(item.argument, state)
        trace.append({"operation": item.operation, "status": "executed"})
    return {"state": state, "trace": trace, "instruction_count": len(program.instructions)}

DEFAULT_PROGRAM = """ARC3 {
👁️ OBSERVE(frame)
🔍 SEGMENT(objects)
🧩 RELATE(objects)
📐 GEOMETRY(objects)
↔️ TRACK(objects)
🧠 HYPOTHESIZE(mechanics)
🔮 PREDICT(legal_actions)
🧪 PROBE(information_gain)
🌳 SEARCH(belief_tree)
🎯 SELECT(best_legal_action)
▶️ ACT(best_legal_action)
✔️ VERIFY(actual_observation)
💾 MEMORIZE(verified_transition)
}"""
