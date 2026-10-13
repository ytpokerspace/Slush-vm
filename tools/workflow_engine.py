#!/usr/bin/env python3
"""Deterministic SHUSH workflow runner with vocabulary-backed emoji aliases.

This reference runner executes only explicitly registered Python handlers.
Emoji are resolved through registry/vocabulary.json and
registry/workflow_aliases.json to exact capability IDs and versions.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]

class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")

Handler = Callable[[dict[str, Any]], Any]
_REF = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_-]*)\.([A-Za-z_][A-Za-z0-9_-]*)$")

def load_json(path: str | Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise WorkflowError("E_FILE_NOT_FOUND", str(path)) from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError("E_JSON_INVALID", f"{path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise WorkflowError("E_SCHEMA", f"{path}: top-level JSON value must be an object")
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
    return checks.get(type_name, lambda x: False)(value)

@dataclass(frozen=True)
class Capability:
    id: str
    version: str
    inputs: Mapping[str, str]
    outputs: Mapping[str, str]
    permissions: tuple[str, ...]
    status: str

class EmojiResolver:
    """Resolve an emoji in an explicit namespace, then map it to an exact capability."""

    def __init__(self, vocabulary: Mapping[str, Any], aliases: Mapping[str, Any]):
        self.vocabulary = list(vocabulary.get("entries", []))
        self.aliases = list(aliases.get("aliases", []))

    def resolve(self, symbol: str, namespace: str) -> dict[str, str]:
        candidates = [
            a for a in self.aliases
            if a.get("symbol") == symbol and a.get("namespace") == namespace
        ]
        if not candidates:
            # Distinguish a known vocabulary token from a missing emoji alias.
            known = [
                e for e in self.vocabulary
                if e.get("symbol") == symbol and e.get("category") == namespace
            ]
            if known:
                raise WorkflowError("E_ALIAS_NOT_REGISTERED",
                                    f"{symbol} is vocabulary syntax in {namespace}, not a workflow capability alias")
            raise WorkflowError("E_ALIAS_NOT_FOUND", f"{symbol} in namespace {namespace}")
        if len(candidates) != 1:
            targets = sorted(f"{a.get('capability_id')}@{a.get('version')}" for a in candidates)
            raise WorkflowError("E_ALIAS_AMBIGUOUS", f"{symbol} in {namespace}: {targets}")
        alias = candidates[0]
        vocab_matches = [
            e for e in self.vocabulary
            if e.get("id") == alias.get("vocabulary_id")
            and e.get("symbol") == symbol
            and e.get("category") == namespace
        ]
        if len(vocab_matches) != 1:
            raise WorkflowError("E_VOCABULARY_MISMATCH",
                                f"alias {symbol} must match exactly one vocabulary entry")
        for field in ("capability_id", "version"):
            if not isinstance(alias.get(field), str) or not alias[field]:
                raise WorkflowError("E_ALIAS_SCHEMA", f"alias {symbol} missing {field}")
        return {"id": alias["capability_id"], "version": alias["version"]}

class WorkflowEngine:
    """Execute linear workflows with exact resolution, typed contracts, and permission grants."""

    def __init__(self, registry: Mapping[str, Any], handlers: Mapping[str, Handler],
                 granted_permissions: set[str] | None = None,
                 resolver: EmojiResolver | None = None):
        self.handlers = dict(handlers)
        self.grants = set(granted_permissions or ())
        self.resolver = resolver
        self.capabilities: dict[tuple[str, str], Capability] = {}
        for raw in registry.get("capabilities", []):
            try:
                cap = Capability(
                    id=raw["id"], version=raw["version"],
                    inputs=raw.get("inputs", {}), outputs=raw.get("outputs", {}),
                    permissions=tuple(raw.get("permissions", [])),
                    status=raw.get("status", "planned"),
                )
            except (KeyError, TypeError) as exc:
                raise WorkflowError("E_REGISTRY_SCHEMA", f"invalid capability contract: {exc}") from exc
            key = (cap.id, cap.version)
            if key in self.capabilities:
                raise WorkflowError("E_DUPLICATE_CAPABILITY", f"{cap.id}@{cap.version}")
            self.capabilities[key] = cap

    def _reference_for_step(self, step: Mapping[str, Any]) -> dict[str, str]:
        raw = step.get("capability")
        symbol = step.get("symbol")
        if symbol is not None:
            namespace = step.get("namespace")
            if not isinstance(namespace, str) or not namespace:
                raise WorkflowError("E_NAMESPACE_REQUIRED", "emoji steps must declare namespace")
            if self.resolver is None:
                raise WorkflowError("E_RESOLVER_UNAVAILABLE", "load vocabulary and workflow aliases first")
            resolved = self.resolver.resolve(symbol, namespace)
            if raw is not None and raw != resolved:
                raise WorkflowError("E_ALIAS_CONFLICT", f"{symbol} resolves to {resolved}, not {raw}")
            return resolved
        if not isinstance(raw, dict):
            raise WorkflowError("E_BAD_REFERENCE", "step needs capability {id, version} or symbol + namespace")
        return raw

    def resolve(self, ref: Mapping[str, Any]) -> Capability:
        cap_id, version = ref.get("id"), ref.get("version")
        if not isinstance(cap_id, str) or not isinstance(version, str):
            raise WorkflowError("E_BAD_REFERENCE", "canonical capability ID and exact version are required")
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
            cap = self.resolve(self._reference_for_step(step))
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
            trace.append({"step": step_id, "symbol": step.get("symbol"),
                          "capability": cap.id, "version": cap.version, "status": "ok"})
        return {"status": "ok", "results": results, "trace": trace}

def demo_engine(root: str | Path = ROOT) -> WorkflowEngine:
    """Load the sample registry and real project vocabulary/alias manifests."""
    root = Path(root)
    registry = load_json(root / "examples" / "demo_capabilities.json")
    vocabulary = load_json(root / "registry" / "vocabulary.json")
    aliases = load_json(root / "registry" / "workflow_aliases.json")
    resolver = EmojiResolver(vocabulary, aliases)
    handlers = {
        "text.normalize": lambda a: {"text": " ".join(a["text"].split())},
        "text.word_count": lambda a: {"count": len(a["text"].split())},
    }
    return WorkflowEngine(registry, handlers, resolver=resolver)

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run a SHUSH workflow using the vocabulary-backed offline demo registry.")
    parser.add_argument("workflow", nargs="?", default="examples/normalize_and_count.workflow.json")
    args = parser.parse_args()
    try:
        result = demo_engine().run(load_json(args.workflow))
    except (OSError, WorkflowError) as exc:
        print(str(exc))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
