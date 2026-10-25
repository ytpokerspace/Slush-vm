"""Experimental runner for the official ARC-AGI-3 Python toolkit.

Install the official toolkit separately (pip install arc-agi). This runner is
intended for smoke-testing the adapter against an environment, not as a strong
game-solving policy. Complex click actions use a configurable fixed coordinate.
"""
from __future__ import annotations

import argparse
import json
from enum import Enum
from typing import Any

from arc3.emoji_solver import Arc3EmojiSolver


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
    """Keep the complete serializable frame plus explicit terminal/progress fields."""
    normalized = to_jsonable(frame)
    if not isinstance(normalized, dict):
        normalized = {"frame": normalized}
    state = getattr(frame, "state", None)
    levels_completed = getattr(frame, "levels_completed", None)
    normalized["__arc3_state"] = getattr(state, "name", str(state)) if state is not None else None
    normalized["__arc3_levels_completed"] = to_jsonable(levels_completed)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-id", default="ls20", help="ARC-AGI-3 game id (default: ls20)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-actions", type=int, default=100)
    parser.add_argument("--click-x", type=int, default=32, help="Fixed x for complex actions")
    parser.add_argument("--click-y", type=int, default=32, help="Fixed y for complex actions")
    parser.add_argument("--render-mode", choices=("terminal", "terminal-fast", "human"))
    parser.add_argument("--save-recording", action="store_true")
    args = parser.parse_args()

    if args.max_actions < 1:
        parser.error("--max-actions must be at least 1")
    if not (0 <= args.click_x <= 63 and 0 <= args.click_y <= 63):
        parser.error("click coordinates must be between 0 and 63")

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

    frame = env.observation_space or env.reset()
    if frame is None:
        parser.exit(2, "Environment did not return an initial observation.\n")

    solver = Arc3EmojiSolver()
    history: list[dict[str, Any]] = []
    steps = 0
    terminal = "action_limit"
    while steps < args.max_actions:
        legal = list(env.action_space or [])
        action_records = [{"name": getattr(action, "name", str(action))} for action in legal]
        observation = frame_observation(frame)
        result = solver.choose_action(observation, action_records, history)
        if result["action"] is None:
            terminal = "no_legal_actions"
            break

        selected_name = result["action"]["name"]
        selected = next(
            (action for action in legal if getattr(action, "name", str(action)) == selected_name),
            None,
        )
        if selected is None:
            terminal = "policy_returned_non_legal_action"
            break

        history.append({"observation": observation, "action": result["action"]})
        action_data = {"x": args.click_x, "y": args.click_y} if selected.is_complex() else None
        next_frame = env.step(selected, data=action_data)
        steps += 1
        if next_frame is None:
            terminal = "environment_returned_no_observation"
            break
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
        score = arcade.get_scorecard()
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
        "policy": "deterministic baseline; not a benchmark-performance claim",
        "scorecard": scorecard,
        "last_state": frame_observation(frame).get("__arc3_state"),
    }, ensure_ascii=False))
    return 0 if terminal == "win" else 1


if __name__ == "__main__":
    raise SystemExit(main())
