import unittest

from arc3.emoji_solver import Arc3EmojiSolver, EMOJI_PROGRAM, grid_summary


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

    def test_reports_repeated_state(self):
        solver = Arc3EmojiSolver(max_repeated_state=2)
        solver.choose_action({"grid": [[0]]}, ["wait"])
        result = solver.choose_action({"grid": [[0]]}, ["wait"])
        self.assertEqual(result["status"], "possible_loop")

    def test_grid_summary_handles_ragged_rows(self):
        summary = grid_summary({"grid": [[0, 1], [1]]})
        self.assertEqual(summary["height"], 2)
        self.assertEqual(summary["widths"], [2, 1])
        self.assertEqual(summary["cell_count"], 3)

    def test_program_is_emoji_native_surface(self):
        self.assertIn("📥", EMOJI_PROGRAM)
        self.assertIn("🎯", EMOJI_PROGRAM)


if __name__ == "__main__":
    unittest.main()
