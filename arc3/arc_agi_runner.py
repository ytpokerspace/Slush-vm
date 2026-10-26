"""Experimental runner for the official ARC-AGI-3 Python toolkit.

Install the official toolkit separately (pip install arc-agi). This runner uses a
deterministic exploratory policy; it does not claim strong or benchmark-level play.
"""
from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import Any

from arc3.emoji_solver import Arc3EmojiSolver
from arc3.visual_policy import infer_navigation, score_navigation_candidates


def to_jsonable(value: Any) -> Any:
    """Convert SDK observations to JSON-safe data without assuming one SDK model."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "model_dump"):
        try:
            return to_jsonable(value.model_dump(mode="json"))
        except TypeError:
            return to_jsonable(value.model_dump())
    if hasattr(value, "dict") and callable(value.dict):
        return to_jsonable(value.dict())
    if hasattr(value, "tolist") and callable(value.tolist):
        return to_jsonable(value.tolist())
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return to_jsonable(vars(value))
    return repr(value)


def frame_observation(frame: Any) -> dict[str, Any]:
    """Keep the full serializable frame plus explicit terminal/progress fields."""
    normalized = to_jsonable(frame)
    if not isinstance(normalized, dict):
        normalized = {"frame": normalized}
    # Prefer the SDK's raw frame attribute over model_dump's serialization. Some
    # SDK/Pydantic versions omit or reshape NumPy frame layers in model_dump output.
    raw_frame = getattr(frame, "frame", None)
    if raw_frame is not None:
        normalized["frame"] = to_jsonable(raw_frame)
    state = getattr(frame, "state", None)
    levels_completed = getattr(frame, "levels_completed", None)
    win_levels = getattr(frame, "win_levels", None)
    normalized["__arc3_state"] = getattr(state, "name", str(state)) if state is not None else None
    normalized["__arc3_levels_completed"] = to_jsonable(levels_completed)
    normalized["__arc3_win_levels"] = to_jsonable(win_levels)
    return normalized


def candidate_click_points(
    observation: Any,
    strategy: str = "foreground",
    center_x: int = 32,
    center_y: int = 32,
    max_points: int = 32,
    previous_observation: Any = None,
) -> list[dict[str, int]]:
    """Generate bounded deterministic click candidates from a serialized frame.

    FrameDataRaw.frame is a stack of 2D layers. Foreground mode prefers changed
    nonzero cells compared with the prior frame, then falls back to all foreground
    cells so stationary relevant objects remain available. Scan and center modes
    remain explicit exploration strategies; this is motion salience, not full
    semantic object detection.
    """
    if strategy == "center":
        return [{"x": center_x, "y": center_y}]
    if strategy == "scan":
        return [{"x": x, "y": y} for y in range(4, 64, 8) for x in range(4, 64, 8)][:max_points]
    if strategy != "foreground":
        raise ValueError(f"unsupported click strategy: {strategy}")

    frame = observation.get("frame") if isinstance(observation, dict) else None
    if not isinstance(frame, list):
        return [{"x": center_x, "y": center_y}]

    # Accept either a stack of 2D layers or a single 2D grid.
    if frame and isinstance(frame[0], list) and frame[0] and not isinstance(frame[0][0], list):
        layers = [frame]
    else:
        layers = frame

    points: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for layer in layers:
        if not isinstance(layer, list):
            continue
        for y, row in enumerate(layer[:64]):
            if not isinstance(row, list):
                continue
            for x, cell in enumerate(row[:64]):
                if cell not in (0, "0", None) and (x, y) not in seen:
                    seen.add((x, y))
                    points.append((x, y))
    if not points:
        return [{"x": center_x, "y": center_y}]
    # Prefer pixels that changed since the prior frame: these are likely to
    # belong to moving or newly active objects. Keep a foreground fallback so
    # stationary goals remain clickable when the scene has no visible motion.
    previous_frame = (
        previous_observation.get("frame")
        if isinstance(previous_observation, dict) else None
    )
    if previous_frame is not None:
        if previous_frame and isinstance(previous_frame[0], list) and previous_frame[0] and not isinstance(previous_frame[0][0], list):
            previous_layers = [previous_frame]
        else:
            previous_layers = previous_frame if isinstance(previous_frame, list) else []
        changed: list[tuple[int, int]] = []
        for layer_index, layer in enumerate(layers):
            if layer_index >= len(previous_layers) or not isinstance(layer, list):
                continue
            prior = previous_layers[layer_index]
            if not isinstance(prior, list):
                continue
            for y, row in enumerate(layer[:64]):
                if not isinstance(row, list) or y >= len(prior) or not isinstance(prior[y], list):
                    continue
                for x, cell in enumerate(row[:64]):
                    if x < len(prior[y]) and cell != prior[y][x] and cell not in (0, "0", None):
                        changed.append((x, y))
        if changed:
            points = list(dict.fromkeys(changed))

    # Evenly sample the discovered positions so large foreground areas don't
    # exhaust the action budget on adjacent cells.
    if len(points) > max_points:
        if max_points == 1:
            points = [points[len(points) // 2]]
        else:
            indices = [round(i * (len(points) - 1) / (max_points - 1)) for i in range(max_points)]
            points = [points[i] for i in indices]
    return [{"x": x, "y": y} for x, y in points]


def make_action_records(legal_actions: list[Any], observation: dict[str, Any],
                        click_strategy: str, center_x: int, center_y: int,
                        max_click_points: int = 32,
                        previous_observation: Any = None) -> list[dict[str, Any]]:
    """Expand complex legal actions into legal action + coordinate candidates."""
    records: list[dict[str, Any]] = []
    points = candidate_click_points(
        observation, click_strategy, center_x, center_y, max_click_points,
        previous_observation,
    )
    for action in legal_actions:
        name = getattr(action, "name", str(action))
        is_complex = callable(getattr(action, "is_complex", None)) and action.is_complex()
        if is_complex:
            records.extend({"name": name, "data": point} for point in points)
        else:
            records.append({"name": name})
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-id", default="ls20", help="ARC-AGI-3 game id (default: ls20)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-actions", type=int, default=100)
    parser.add_argument("--click-x", type=int, default=32, help="Center/fallback x coordinate")
    parser.add_argument("--click-y", type=int, default=32, help="Center/fallback y coordinate")
    parser.add_argument("--click-strategy", choices=("foreground", "scan", "center"), default="foreground")
    parser.add_argument("--max-click-points", type=int, default=32)
    parser.add_argument("--render-mode", choices=("terminal", "terminal-fast", "human"))
    parser.add_argument("--save-recording", action="store_true")
    args = parser.parse_args()

    if args.max_actions < 1:
        parser.error("--max-actions must be at least 1")
    if not (0 <= args.click_x <= 63 and 0 <= args.click_y <= 63):
        parser.error("click coordinates must be between 0 and 63")
    if not (1 <= args.max_click_points <= 4096):
        parser.error("--max-click-points must be between 1 and 4096")

    try:
        import arc_agi
        from arcengine import GameState
    except ImportError as exc:
        parser.exit(2, f"Missing optional dependency: {exc}. Install with: pip install arc-agi\n")

    arcade = arc_agi.Arcade()
    env = arcade.make(
        args.game_id,
        seed=args.seed,
        render_mode=args.render_mode,
        save_recording=args.save_recording,
    )
    if env is None:
        parser.exit(2, f"Could not create ARC environment {args.game_id!r}. Check SDK access and game id.\n")

    frame = env.observation_space
    if frame is None:
        frame = env.reset()
    if frame is None:
        parser.exit(2, "Environment did not return an initial observation.\n")

    solver = Arc3EmojiSolver()
    history: list[dict[str, Any]] = []
    steps = 0
    navigation_steps = 0
    last_navigation = None
    previous_observation = None
    terminal = "action_limit"
    while steps < args.max_actions:
        legal = list(env.action_space or [])
        observation = frame_observation(frame)
        action_records = make_action_records(
            legal, observation, args.click_strategy, args.click_x, args.click_y,
            args.max_click_points, previous_observation,
        )
        navigation = infer_navigation(observation)
        action_records = score_navigation_candidates(action_records, navigation)
        last_navigation = navigation
        result = solver.choose_action(observation, action_records, history)
        if result["action"] is None:
            terminal = "no_legal_actions"
            break

        selected_record = result["action"]
        selected_name = selected_record["name"]
        selected = next(
            (action for action in legal if getattr(action, "name", str(action)) == selected_name),
            None,
        )
        if selected is None:
            terminal = "policy_returned_non_legal_action"
            break

        if navigation is not None and selected_name == navigation.get("action"):
            navigation_steps += 1
        history.append({
            "observation": observation,
            "action": selected_record,
            "navigation": navigation,
        })
        action_data = selected_record.get("data") if selected.is_complex() else None
        if selected.is_complex() and not isinstance(action_data, dict):
            action_data = {"x": args.click_x, "y": args.click_y}
        next_frame = env.step(selected, data=action_data)
        steps += 1
        if next_frame is None:
            terminal = "environment_returned_no_observation"
            break
        previous_observation = observation
        frame = next_frame
        state = getattr(frame, "state", None)
        state_name = getattr(state, "name", str(state)).upper() if state is not None else ""
        if state == GameState.WIN or state_name == "WIN":
            terminal = "win"
            break
        if state == GameState.GAME_OVER or state_name == "GAME_OVER":
            terminal = "game_over"
            break

    scorecard = None
    try:
        score = arcade.close_scorecard()
        if score is not None:
            scorecard = to_jsonable(score)
    except Exception as exc:
        scorecard = {"unavailable": str(exc)}

    print(json.dumps({
        "game_id": args.game_id,
        "seed": args.seed,
        "steps": steps,
        "terminal": terminal,
        "won": terminal == "win",
        "levels_completed": getattr(frame, "levels_completed", None),
        "win_levels": getattr(frame, "win_levels", None),
        "policy": "observation-only visual target heuristic with deterministic exploration fallback",
        "navigation_steps": navigation_steps,
        "last_navigation": last_navigation,
        "click_strategy": args.click_strategy,
        "scorecard": scorecard,
        "last_state": frame_observation(frame).get("__arc3_state"),
    }, ensure_ascii=False))
    # A completed run is a successful benchmark execution even if it did not win.
    # The result JSON distinguishes "won" from "ran successfully".
    return 0 if steps > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
