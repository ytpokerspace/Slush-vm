#!/usr/bin/env python3
"""Minimal deterministic SHUSH workflow runner.

Emoji are surface aliases; canonical capability IDs and exact versions carry
identity. This prototype intentionally executes only explicitly registered
Python handlers and never evaluates generated code.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")

Handler = Callable[[dict[str, Any]], Any]
_REF = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_-]*)\.([A-Za-z_][A-Za-z0-9_-]*)$")

def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise WorkflowError("E_SCHEMA", "top-level JSON value must be an object")
    return data

def _type_ok(value: Any, type_name: str) -> bool:
    checks = {
        "STR": lambda x: isinstance(x, str),
        "NUM": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
        "BOOL": lambda x: isinstance(x, bool),
        "LIST": lambda x: isinstance(x, list),
        "MAP": lambda x: isinstance(x, dict),
        "JSON": lambda x: True,
        "ANY": lambda x: True,
    }
    return checks.get(type_name, lambda x: True)(value)

@dataclass(frozen=True)
class Capability:
    id: str
    version: str
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    permissions: tuple[str, ...]
    status: str

class WorkflowEngine:
    """Execute a linear workflow with exact resolution and explicit grants."""

    def __init__(self, registry: Mapping[str, Any], handlers: Mapping[str, Handler],
                 granted_permissions: set[str] | None = None):
        self.handlers = dict(handlers)
        self.grants = set(granted_permissions or ())
        self.capabilities: dict[tuple[str, str], Capability] = {}
        for raw in registry.get("capabilities", []):
            cap = Capability(
                id=raw["id"], version=raw["version"],
                inputs=raw.get("inputs", {}), outputs=raw.get("outputs", {}),
                permissions=tuple(raw.get("permissions", [])),
                status=raw.get("status", "planned"),
            )
            key = (cap.id, cap.version)
            if key in self.capabilities:
                raise WorkflowError("E_DUPLICATE_CAPABILITY", f"{cap.id}@{cap.version}")
            self.capabilities[key] = cap

    def resolve(self, ref: Mapping[str, Any]) -> Capability:
        cap_id, version = ref.get("id"), ref.get("version")
        if not isinstance(cap_id, str) or not isinstance(version, str):
            raise WorkflowError("E_BAD_REFERENCE", "each step needs string id and exact version")
        cap = self.capabilities.get((cap_id, version))
        if cap is None:
            raise WorkflowError("E_CAPABILITY_NOT_FOUND", f"{cap_id}@{version}")
        if cap.status != "tested":
            raise WorkflowError("E_CAPABILITY_UNVERIFIED", f"{cap_id}@{version} status={cap.status}")
        if cap_id not in self.handlers:
            raise WorkflowError("E_IMPLEMENTATION_MISSING", cap_id)
        missing = sorted(set(cap.permissions) - self.grants)
        if missing:
            raise WorkflowError("E_PERMISSION_DENIED", f"{cap_id} requires {', '.join(missing)}")
        return cap

    @staticmethod
    def _resolve_value(value: Any, results: Mapping[str, Any]) -> Any:
        if isinstance(value, str):
            match = _REF.fullmatch(value)
            if match:
                step_id, field = match.groups()
                if step_id not in results:
                    raise WorkflowError("E_REFERENCE_NOT_FOUND", value)
                result = results[step_id]
                if not isinstance(result, dict) or field not in result:
                    raise WorkflowError("E_OUTPUT_NOT_FOUND", value)
                return result[field]
        if isinstance(value, list):
            return [WorkflowEngine._resolve_value(v, results) for v in value]
        if isinstance(value, dict):
            return {k: WorkflowEngine._resolve_value(v, results) for k, v in value.items()}
        return value

    def run(self, workflow: Mapping[str, Any]) -> dict[str, Any]:
        steps = workflow.get("steps")
        if not isinstance(steps, list) or not steps:
            raise WorkflowError("E_WORKFLOW_EMPTY", "workflow must contain a non-empty steps list")
        results: dict[str, Any] = {}
        trace: list[dict[str, Any]] = []
        for step in steps:
            if not isinstance(step, dict):
                raise WorkflowError("E_STEP_SCHEMA", "each step must be an object")
            step_id = step.get("id")
            if not isinstance(step_id, str) or not step_id or step_id in results:
                raise WorkflowError("E_STEP_ID", "step IDs must be non-empty and unique")
            cap = self.resolve(step.get("capability", {}))
            args = self._resolve_value(step.get("args", {}), results)
            if not isinstance(args, dict):
                raise WorkflowError("E_INPUT_SCHEMA", f"{step_id}: args must be an object")
            missing = set(cap.inputs) - set(args)
            extra = set(args) - set(cap.inputs)
            if missing or extra:
                raise WorkflowError("E_INPUT_SCHEMA", f"{step_id}: missing={sorted(missing)}, extra={sorted(extra)}")
            for name, expected in cap.inputs.items():
                if not _type_ok(args[name], expected):
                    raise WorkflowError("E_INPUT_TYPE", f"{step_id}.{name} expected {expected}")
            output = self.handlers[cap.id](args)
            if cap.outputs:
                if not isinstance(output, dict):
                    raise WorkflowError("E_OUTPUT_SCHEMA", f"{step_id}: handler must return an object")
                missing_out = set(cap.outputs) - set(output)
                extra_out = set(output) - set(cap.outputs)
                if missing_out or extra_out:
                    raise WorkflowError("E_OUTPUT_SCHEMA", f"{step_id}: missing={sorted(missing_out)}, extra={sorted(extra_out)}")
                for name, expected in cap.outputs.items():
                    if not _type_ok(output[name], expected):
                        raise WorkflowError("E_OUTPUT_TYPE", f"{step_id}.{name} expected {expected}")
            results[step_id] = output
            trace.append({"step": step_id, "capability": cap.id, "version": cap.version, "status": "ok"})
        return {"status": "ok", "results": results, "trace": trace}

def demo_engine() -> WorkflowEngine:
    """Small offline demo; these handlers are examples, not production integrations."""
    registry = {"capabilities": [
        {"id": "text.normalize", "version": "1.0.0", "inputs": {"text": "STR"},
         "outputs": {"text": "STR"}, "permissions": [], "status": "tested"},
        {"id": "text.word_count", "version": "1.0.0", "inputs": {"text": "STR"},
         "outputs": {"count": "NUM"}, "permissions": [], "status": "tested"},
    ]}
    handlers = {
        "text.normalize": lambda a: {"text": " ".join(a["text"].split())},
        "text.word_count": lambda a: {"count": len(a["text"].split())},
    }
    return WorkflowEngine(registry, handlers)

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run a SHUSH JSON workflow (offline demo registry).")
    parser.add_argument("workflow", help="path to workflow JSON")
    args = parser.parse_args()
    try:
        result = demo_engine().run(load_json(args.workflow))
    except (OSError, json.JSONDecodeError, WorkflowError) as exc:
        print(str(exc))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
