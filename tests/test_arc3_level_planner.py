import unittest

from arc3.level_planner import LevelPlanningMemory


class LevelPlanningMemoryTests(unittest.TestCase):
    def test_partitions_are_separate_and_present(self):
        memory = LevelPlanningMemory()
        self.assertEqual(
            set(memory.partitions),
            {
                "level_progress", "scene_state", "goal_hypotheses",
                "active_plan", "action_outcomes", "uncertainties",
            },
        )

    def test_level_completion_requires_explicit_progress_or_win_signal(self):
        memory = LevelPlanningMemory()
        snapshot = memory.update_observation({"__arc3_state": "ACTIVE"})
        self.assertFalse(snapshot["level_progress"]["completion_confirmed"])
        snapshot = memory.update_observation({
            "__arc3_state": "ACTIVE",
            "__arc3_levels_completed": 1,
            "__arc3_win_levels": 5,
        })
        self.assertEqual(snapshot["level_progress"]["levels_completed"], 1)
        self.assertEqual(snapshot["level_progress"]["win_levels"], 5)
        self.assertTrue(snapshot["level_progress"]["completion_confirmed"])

    def test_plan_and_goal_are_stored_separately_from_progress(self):
        memory = LevelPlanningMemory()
        snapshot = memory.update_observation(
            {"frame": [[[0, 1], [2, 3]]]},
            {"action": "ACTION1", "target_center": [1, 0], "step_size": 2},
        )
        self.assertEqual(snapshot["active_plan"][0]["action"], "ACTION1")
        self.assertEqual(snapshot["goal_hypotheses"][0]["target_center"], [1, 0])
        self.assertEqual(snapshot["scene_state"]["frame_shape"], [1, 2, 2])
        self.assertEqual(snapshot["level_progress"]["levels_completed"], 0)

    def test_no_navigation_records_uncertainty_instead_of_fake_plan(self):
        memory = LevelPlanningMemory()
        snapshot = memory.update_observation({"grid": [[0, 1]]}, None)
        self.assertEqual(snapshot["active_plan"], [])
        self.assertTrue(snapshot["uncertainties"])

    def test_action_outcome_records_only_observed_change(self):
        memory = LevelPlanningMemory()
        snapshot = memory.record_action("ACTION1", {"grid": [[0]]}, {"grid": [[1]]})
        self.assertTrue(snapshot["action_outcomes"][0]["observation_changed"])
        self.assertEqual(snapshot["action_outcomes"][0]["interpretation"], "state changed after action")


if __name__ == "__main__":
    unittest.main()
