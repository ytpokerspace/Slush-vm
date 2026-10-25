import json
import subprocess
import sys
import unittest
from enum import Enum
from types import SimpleNamespace

from arc3.arc_agi_runner import frame_observation, to_jsonable
from arc3.emoji_solver import Arc3EmojiSolver, EMOJI_PROGRAM, grid_summary, stable_key, state_key


class Arc3EmojiSolverTests(unittest.TestCase):
    def test_selects_only_a_legal_action(self):
        legal = [{"button": "left"}, {"button": "right"}]
        result = Arc3EmojiSolver().choose_action({"grid": [[0, 1]]}, legal)
        self.assertIn(result["action"], legal)
        self.assertEqual(result["status"], "ok")

    def test_uses_explicit_action_score(self):
        legal = [{"id": "low", "score": 0.1}, {"id": "high", "score": 0.9}]
        result = Arc3EmojiSolver().choose_action({}, legal)
        self.assertEqual(result["action"]["id"], "high")

    def test_uses_priority_when_score_missing(self):
        legal = [{"id": "low", "priority": 1}, {"id": "high", "priority": 2}]
        self.assertEqual(Arc3EmojiSolver().choose_action({}, legal)["action"]["id"], "high")

    def test_prefers_untried_action_for_same_state(self):
        solver = Arc3EmojiSolver()
        observation = {"grid": [[0, 1], [1, 0]]}
        legal = ["north", "south"]
        first = solver.choose_action(observation, legal)["action"]
        second = solver.choose_action(observation, legal)["action"]
        self.assertNotEqual(first, second)

    def test_reports_empty_action_space(self):
        result = Arc3EmojiSolver().choose_action({}, [])
        self.assertIsNone(result["action"])
        self.assertEqual(result["status"], "no_legal_actions")

    def test_empty_action_space_does_not_advance_turn(self):
        solver = Arc3EmojiSolver()
        solver.choose_action({}, [])
        self.assertEqual(solver.turns, 0)

    def test_reports_repeated_state(self):
        solver = Arc3EmojiSolver(max_repeated_state=2)
        solver.choose_action({"grid": [[0]]}, ["wait"])
        result = solver.choose_action({"grid": [[0]]}, ["wait"])
        self.assertEqual(result["status"], "possible_loop")

    def test_state_change_resets_per_state_attempt_tracking(self):
        solver = Arc3EmojiSolver()
        first = solver.choose_action({"x": 1}, ["a", "b"])["action"]
        second = solver.choose_action({"x": 2}, ["a", "b"])["action"]
        self.assertEqual(first, second)

    def test_equal_scores_use_input_order(self):
        actions = [{"id": "first", "score": 1}, {"id": "second", "score": 1}]
        self.assertEqual(Arc3EmojiSolver().choose_action({}, actions)["action"]["id"], "first")

    def test_boolean_is_not_treated_as_numeric_score(self):
        actions = [{"id": "boolean", "score": True}, {"id": "number", "score": 0.5}]
        self.assertEqual(Arc3EmojiSolver().choose_action({}, actions)["action"]["id"], "number")

    def test_negative_scores_are_ranked(self):
        actions = [{"id": "worse", "score": -3}, {"id": "better", "score": -1}]
        self.assertEqual(Arc3EmojiSolver().choose_action({}, actions)["action"]["id"], "better")

    def test_only_actions_in_legal_list_can_be_selected(self):
        actions = [{"id": "a", "score": 0}, {"id": "b", "score": 99}]
        result = Arc3EmojiSolver().choose_action({}, actions)
        self.assertIn(result["action"], actions)

    def test_retries_untried_lower_scored_action_on_same_state(self):
        solver = Arc3EmojiSolver()
        observation = {"room": 1}
        actions = [{"id": "best", "score": 10}, {"id": "next", "score": 5}]
        self.assertEqual(solver.choose_action(observation, actions)["action"]["id"], "best")
        self.assertEqual(solver.choose_action(observation, actions)["action"]["id"], "next")

    def test_deterministic_fallback_after_all_actions_attempted(self):
        solver = Arc3EmojiSolver()
        observation = {"room": 1}
        actions = ["a", "b"]
        solver.choose_action(observation, actions)
        solver.choose_action(observation, actions)
        result = solver.choose_action(observation, actions)
        self.assertIn(result["action"], actions)

    def test_grid_summary_handles_ragged_rows(self):
        summary = grid_summary({"grid": [[0, 1], [1]]})
        self.assertEqual(summary["height"], 2)
        self.assertEqual(summary["widths"], [2, 1])
        self.assertEqual(summary["cell_count"], 3)

    def test_grid_summary_supports_board_alias(self):
        self.assertEqual(grid_summary({"board": [[7]]})["cell_count"], 1)

    def test_grid_summary_empty_grid(self):
        summary = grid_summary({"grid": []})
        self.assertEqual(summary["height"], 0)
        self.assertEqual(summary["cell_count"], 0)

    def test_grid_summary_non_grid_observation(self):
        summary = grid_summary({"player": {"x": 1}})
        self.assertEqual(summary["kind"], "structured")
        self.assertIn("player", summary["keys"])

    def test_grid_summary_scalar_observation(self):
        self.assertEqual(grid_summary("observation"), {"kind": "str"})

    def test_stable_key_ignores_dictionary_insertion_order(self):
        self.assertEqual(stable_key({"a": 1, "b": 2}), stable_key({"b": 2, "a": 1}))

    def test_state_key_distinguishes_different_observations(self):
        self.assertNotEqual(state_key({"grid": [[0]]}), state_key({"grid": [[1]]}))

    def test_diagnostics_include_legal_count_and_turn(self):
        result = Arc3EmojiSolver().choose_action({}, ["a", "b"])
        self.assertEqual(result["diagnostics"]["legal_action_count"], 2)
        self.assertEqual(result["diagnostics"]["turn"], 1)

    def test_history_length_is_reported(self):
        result = Arc3EmojiSolver().choose_action({}, ["a"], history=[{"action": "x"}])
        self.assertEqual(result["diagnostics"]["history_length"], 1)

    def test_emoji_program_is_present_in_response(self):
        result = Arc3EmojiSolver().choose_action({}, ["a"])
        self.assertEqual(result["program"], EMOJI_PROGRAM)

    def test_cli_valid_request_emits_json(self):
        request = {"observation": {"grid": [[0, 1]]}, "legal_actions": [{"button": "left"}]}
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input=json.dumps(request), text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["action"], {"button": "left"})

    def test_cli_rejects_non_object_json(self):
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input="[]", text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("request must be a JSON object", json.loads(process.stdout)["error"])

    def test_cli_rejects_missing_observation(self):
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input='{"legal_actions":[]}', text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("missing required field", json.loads(process.stdout)["error"])

    def test_cli_rejects_non_array_legal_actions(self):
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input='{"observation":{},"legal_actions":{}}', text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("legal_actions must be a JSON array", json.loads(process.stdout)["error"])

    def test_cli_rejects_malformed_json(self):
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input="{not json", text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("invalid JSON input", json.loads(process.stdout)["error"])


    def test_state_round_trip_preserves_attempts_and_turn_count(self):
        solver = Arc3EmojiSolver()
        observation = {"room": 1}
        actions = ["left", "right"]
        first = solver.choose_action(observation, actions)["action"]
        restored = Arc3EmojiSolver.from_state(solver.to_state())
        second = restored.choose_action(observation, actions)["action"]
        self.assertNotEqual(first, second)
        self.assertEqual(restored.turns, 2)

    def test_history_reconstruction_skips_records_without_observation(self):
        solver = Arc3EmojiSolver()
        solver.restore_history([{"action": "left"}, {"observation": {"x": 1}, "action": "left"}])
        chosen = solver.choose_action({"x": 1}, ["left", "right"])["action"]
        self.assertEqual(chosen, "right")
        self.assertEqual(solver.turns, 2)

    def test_history_reconstruction_restores_revisit_detection(self):
        solver = Arc3EmojiSolver(max_repeated_state=3)
        history = [
            {"observation": {"room": 1}, "action": "a"},
            {"observation": {"room": 1}, "action": "b"},
        ]
        solver.restore_history(history)
        result = solver.choose_action({"room": 1}, ["a", "b", "c"])
        self.assertEqual(result["status"], "possible_loop")
        self.assertEqual(result["diagnostics"]["state_revisits"], 2)

    def test_invalid_saved_state_resets_safely(self):
        solver = Arc3EmojiSolver.from_state({"schema_version": 999, "turns": 10})
        self.assertEqual(solver.turns, 0)
        self.assertEqual(solver.seen_states, {})

    def test_saved_state_is_json_serializable(self):
        solver = Arc3EmojiSolver()
        solver.choose_action({"grid": [[0]]}, ["a", "b"])
        self.assertEqual(json.loads(json.dumps(solver.to_state()))["schema_version"], 1)

    def test_cli_emits_state_for_restart(self):
        request = {"observation": {"room": 1}, "legal_actions": ["left", "right"]}
        first = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input=json.dumps(request), text=True, capture_output=True, check=False,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        first_result = json.loads(first.stdout)
        second_request = {**request, "solver_state": first_result["solver_state"]}
        second = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input=json.dumps(second_request), text=True, capture_output=True, check=False,
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(first_result["action"], json.loads(second.stdout)["action"])

    def test_cli_rejects_non_array_history(self):
        process = subprocess.run(
            [sys.executable, "arc3/emoji_solver.py"],
            input='{"observation":{},"legal_actions":[],"history":{}}',
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("history must be a JSON array", json.loads(process.stdout)["error"])


    def test_sdk_runner_helpers_import_without_optional_sdk(self):
        self.assertTrue(callable(to_jsonable))
        self.assertTrue(callable(frame_observation))

    def test_sdk_runner_serializes_nested_enum_values(self):
        class ExampleState(Enum):
            ACTIVE = 1
        result = to_jsonable({"state": ExampleState.ACTIVE, "values": [1, 2]})
        self.assertEqual(result, {"state": "ACTIVE", "values": [1, 2]})

    def test_frame_observation_preserves_state_and_progress(self):
        class ExampleState(Enum):
            WIN = 1
        frame = SimpleNamespace(state=ExampleState.WIN, levels_completed=2, grid=[[0, 1]])
        result = frame_observation(frame)
        self.assertEqual(result["__arc3_state"], "WIN")
        self.assertEqual(result["__arc3_levels_completed"], 2)
        self.assertEqual(result["grid"], [[0, 1]])


    def test_unscored_legal_actions_are_not_starved_by_scored_actions(self):
        solver = Arc3EmojiSolver()
        observation = {"room": "mixed"}
        actions = [{"id": "scored", "score": 10}, {"id": "unscored"}]
        self.assertEqual(solver.choose_action(observation, actions)["action"]["id"], "scored")
        self.assertEqual(solver.choose_action(observation, actions)["action"]["id"], "unscored")

    def test_non_finite_scores_are_ignored(self):
        actions = [
            {"id": "nan", "score": float("nan")},
            {"id": "infinite", "score": float("inf")},
            {"id": "finite", "score": 0.5},
        ]
        self.assertEqual(Arc3EmojiSolver().choose_action({}, actions)["action"]["id"], "finite")


if __name__ == "__main__":
    unittest.main()
