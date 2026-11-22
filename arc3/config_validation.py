"""Dependency-free validation for the Hyper Pipeline v3.3 ARC profile.

This validates configuration consistency and compatibility with the existing
ARC-AGI-3 agent interface. It does not execute an environment, download models,
or run benchmarks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arc3.cognitive_agent import Arc3CognitiveAgent


DEFAULT_CONFIG = Path(__file__).with_name("config") / "hyper_pipeline_v3_3.json"
SUPPORTED_PRECISIONS = {"auto", "bf16", "fp16", "fp8_e4m3", "int8", "nf4", "awq_int4"}
SUPPORTED_BACKENDS = {"auto", "pytorch", "triton_optional"}
MAX_RUNNER_DEPTH = 6
MAX_RUNNER_SIMULATIONS = 512


def _at(data: dict[str, Any], *path: str) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def validate_config(config: dict[str, Any]) -> list[str]:
    """Return actionable validation errors; an empty list means structurally valid."""
    errors: list[str] = []

    if config.get("version") != "3.3":
        errors.append("version must be '3.3'")
    if config.get("engine_id") != "hyper_pipeline_v3":
        errors.append("engine_id must be 'hyper_pipeline_v3'")
    if config.get("target") != "arc-agi-3":
        errors.append("target must be 'arc-agi-3'")
    if config.get("deployment") != "consumer_hardware":
        errors.append("deployment must be 'consumer_hardware'")

    policy = config.get("execution_policy", {})
    for key in (
        "paid_api_calls", "cloud_gpu_provisioning", "external_network_calls",
        "automatic_training", "automatic_live_benchmark", "automatic_deployment",
        "automatic_pull_request_merge",
    ):
        if policy.get(key) is not False:
            errors.append(f"execution_policy.{key} must be false")
    if policy.get("budget_usd") != 0:
        errors.append("execution_policy.budget_usd must be 0")

    model = config.get("model", {})
    if model.get("enabled") is not False:
        errors.append("model.enabled must be false for the default ARC-first profile")
    if model.get("default_profile") != "none":
        errors.append("model.default_profile must be 'none'")
    inference = model.get("inference_constraints", {})
    for key in ("external_api", "network_required", "paid_services"):
        if inference.get(key) is not False:
            errors.append(f"model.inference_constraints.{key} must be false")
    if inference.get("model_calls_required_for_solver") is not False:
        errors.append("the native ARC solver must not require model calls")

    profiles = model.get("profiles", {})
    consumer = profiles.get("consumer_local", {})
    if consumer.get("enabled") is not False:
        errors.append("model.profiles.consumer_local.enabled must be false until explicitly configured")
    if consumer.get("precision") not in SUPPORTED_PRECISIONS:
        errors.append("consumer_local.precision must be a supported explicit format or 'auto'")
    if consumer.get("max_context_tokens", 0) < 1 or consumer.get("max_context_tokens", 0) > 8192:
        errors.append("consumer_local.max_context_tokens must be between 1 and 8192")
    research = profiles.get("research_server", {})
    if research.get("enabled") is not False:
        errors.append("the 70B research_server profile must remain disabled in consumer mode")
    if research.get("precision") == "fp8_e4m3" and research.get("quantization") == "awq":
        errors.append("FP8 weights and AWQ 4-bit weights must be separate profiles")

    solver = config.get("arc_solver", {})
    if solver.get("enabled") is not True:
        errors.append("arc_solver.enabled must be true")
    env = solver.get("environment", {})
    for key in ("legal_actions_only", "record_observations", "preserve_terminal_states", "reject_invalid_actions"):
        if env.get(key) is not True:
            errors.append(f"arc_solver.environment.{key} must be true")

    world = solver.get("world_model", {})
    if world.get("unknown_transition_policy") != "conservative_leaf":
        errors.append("world_model.unknown_transition_policy must be 'conservative_leaf'")
    if world.get("invented_successors") is not False:
        errors.append("world_model.invented_successors must be false")

    studio = solver.get("strategy_studio", {})
    if studio.get("generation_rounds") != 2:
        errors.append("strategy_studio.generation_rounds must be 2")
    if studio.get("refinement_passes") != 4:
        errors.append("strategy_studio.refinement_passes must be 4")

    mcts = solver.get("mcts", {})
    depth = mcts.get("default_depth")
    simulations = mcts.get("default_simulations")
    max_depth = mcts.get("maximum_depth")
    max_simulations = mcts.get("maximum_simulations")
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= MAX_RUNNER_DEPTH:
        errors.append(f"mcts.default_depth must be an integer from 1 to {MAX_RUNNER_DEPTH}")
    if not isinstance(simulations, int) or isinstance(simulations, bool) or not 1 <= simulations <= MAX_RUNNER_SIMULATIONS:
        errors.append(f"mcts.default_simulations must be an integer from 1 to {MAX_RUNNER_SIMULATIONS}")
    if not isinstance(max_depth, int) or not isinstance(depth, int) or max_depth < depth or max_depth > MAX_RUNNER_DEPTH:
        errors.append("mcts.maximum_depth must be >= default_depth and <= 6")
    if not isinstance(max_simulations, int) or not isinstance(simulations, int) or max_simulations < simulations or max_simulations > MAX_RUNNER_SIMULATIONS:
        errors.append("mcts.maximum_simulations must be >= default_simulations and <= 512")
    if mcts.get("prior_semantics") != "ranking_preference":
        errors.append("MCTS priors must be labelled 'ranking_preference', not win probabilities")
    unknown = mcts.get("unknown_transition", {})
    if unknown.get("simulate") is not False:
        errors.append("MCTS must not simulate unknown transitions")

    action_selection = solver.get("action_selection", {})
    for key in ("require_current_legal_action", "reject_unknown_action"):
        if action_selection.get(key) is not True:
            errors.append(f"arc_solver.action_selection.{key} must be true")

    io = config.get("io_pipeline", {})
    archive = io.get("source_archive", {})
    for key in ("immutable", "verify_reconstruction"):
        if archive.get(key) is not True:
            errors.append(f"io_pipeline.source_archive.{key} must be true")
    if archive.get("hash_algorithm") != "sha256":
        errors.append("io_pipeline.source_archive.hash_algorithm must be 'sha256'")
    compression = io.get("cascade_compression", {})
    if compression.get("preserve_original") is not True or compression.get("preserve_exact_reconstruction") is not True:
        errors.append("compression must preserve original source and exact reconstruction")
    hydration = io.get("lazy_context_hydration", {})
    if hydration.get("chunk_unit") != "tokens":
        errors.append("lazy_context_hydration.chunk_unit must be 'tokens'")
    if hydration.get("retrieval_backend") != "local_vector_index":
        errors.append("lazy_context_hydration must use a local retrieval backend")

    if config.get("fine_tuning", {}).get("enabled") is not False:
        errors.append("fine_tuning.enabled must be false in the default profile")

    compute = config.get("computation_engine", {})
    if compute.get("backend") not in SUPPORTED_BACKENDS:
        errors.append(f"computation_engine.backend must be one of {sorted(SUPPORTED_BACKENDS)}")
    memory_fraction = _at(config, "computation_engine", "memory", "gpu_memory_fraction")
    if not isinstance(memory_fraction, (int, float)) or isinstance(memory_fraction, bool) or not 0 < memory_fraction <= 0.70:
        errors.append("gpu_memory_fraction must be > 0 and <= 0.70")
    if _at(config, "computation_engine", "inference", "speculative_decoding", "enabled") is not False:
        errors.append("speculative decoding must remain disabled until measured")
    if _at(config, "computation_engine", "inference", "prefix_caching", "enabled") is not False:
        errors.append("prefix caching must remain disabled until measured")

    evaluation = config.get("evaluation", {})
    if evaluation.get("execution_mode") != "offline_first":
        errors.append("evaluation.execution_mode must be 'offline_first'")
    if _at(config, "evaluation", "live_benchmark", "enabled") is not False:
        errors.append("live ARC-AGI-3 benchmark must remain disabled")
    if _at(config, "evaluation", "live_benchmark", "require_explicit_authorization") is not True:
        errors.append("live benchmark must require explicit authorization")

    return errors


def validate_solver_compatibility(config: dict[str, Any]) -> list[str]:
    """Check configured defaults against the current in-repository agent interface."""
    errors: list[str] = []
    mcts = _at(config, "arc_solver", "mcts") or {}
    agent = Arc3CognitiveAgent()
    if mcts.get("default_depth") != agent.mcts_depth:
        errors.append(
            f"configured MCTS depth ({mcts.get('default_depth')}) does not match "
            f"Arc3CognitiveAgent default ({agent.mcts_depth})"
        )
    if mcts.get("default_simulations") != agent.mcts_simulations:
        errors.append(
            f"configured MCTS simulations ({mcts.get('default_simulations')}) do not match "
            f"Arc3CognitiveAgent default ({agent.mcts_simulations})"
        )
    return errors


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    """Load a JSON configuration (also valid YAML 1.2 syntax) without dependencies."""
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("configuration root must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"Configuration load failed: {exc}\n")

    errors = validate_config(config) + validate_solver_compatibility(config)
    if errors:
        print("Hyper Pipeline v3.3 configuration: INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Hyper Pipeline v3.3 configuration: VALID")
    print("ARC agent defaults match; no environment, model, or benchmark was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
