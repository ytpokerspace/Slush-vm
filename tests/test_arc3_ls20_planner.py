"""Observation-only tests for the ARC-AGI-3 ls20 key/lock planner."""
from __future__ import annotations

import unittest

from arc3.ls20_planner import infer_ls20_plan, _rotate_clockwise

CURRENT_KEY = [
    [1, 1, 1],
    [1, 0, 0],
    [1, 0, 1],
]
TARGET_LOCK = [
    [1, 1, 1],
    [0, 0, 1],
    [1, 0, 1],
]


def make_level_one_frame(key_pattern, player_center=(36, 47)):
    grid = [[4 for _ in range(64)] for _ in range(64)]

    # Walkable green floor, with the central notch that forces the upper route.
    for y in range(25, 50):
        for x in range(14, 54):
            grid[y][x] = 3
    for y in range(30, 45):
        for x in range(29, 34):
            grid[y][x] = 4
    for y in range(17, 25):
        for x in range(34, 39):
            grid[y][x] = 3

    # Lock panel and its 3x3 reference pattern.
    for y in range(8, 17):
        for x in range(32, 41):
            grid[y][x] = 5
    for x in range(32, 41):
        grid[8][x] = 3
        grid[16][x] = 3
    for y in range(8, 17):
        grid[y][32] = 3
        grid[y][40] = 3
    for y, row in enumerate(TARGET_LOCK):
        for x, value in enumerate(row):
            if value:
                grid[11 + y][35 + x] = 9

    # Current-key HUD: each logical cell is rendered as a 2x2 pixel block.
    for y in range(53, 63):
        for x in range(1, 11):
            grid[y][x] = 5
    for y, row in enumerate(key_pattern):
        for x, value in enumerate(row):
            if value:
                for dy in range(2):
                    for dx in range(2):
                        grid[55 + 2 * y + dy][3 + 2 * x + dx] = 9

    # Small rotation tile in the central-left room.
    for x, y in ((21, 31), (21, 32), (22, 32)):
        grid[y][x] = 0
    for x, y in ((20, 32), (21, 33)):
        grid[y][x] = 1

    # Moving player sprite, 5x5 pixels.
    cx, cy = player_center
    for y in range(cy - 2, cy + 3):
        for x in range(cx - 2, cx + 3):
            grid[y][x] = 12 if y < cy else 9

    return {"frame": grid}


class LS20PlannerTests(unittest.TestCase):
    def test_clockwise_rotation_matches_level_one_lock(self):
        self.assertEqual(_rotate_clockwise(CURRENT_KEY), TARGET_LOCK)

    def test_routes_to_rotation_tile_when_key_does_not_match(self):
        plan = infer_ls20_plan(make_level_one_frame(CURRENT_KEY))
        self.assertIsNotNone(plan)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["stage"], "visit_rotation_switch")
        self.assertEqual(plan["key_rotation_steps"], 1)
        self.assertEqual(plan["player_center"], [36, 47])
        self.assertEqual(plan["target_center"], [21, 32])
        self.assertEqual(plan["navigation"]["action"], "ACTION3")
        self.assertEqual(plan["walkable_color"], 3)

    def test_routes_from_rotation_tile_to_lock_after_key_matches(self):
        rotated_key = _rotate_clockwise(CURRENT_KEY)
        plan = infer_ls20_plan(
            make_level_one_frame(rotated_key, player_center=(21, 32))
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["stage"], "reach_matching_door")
        self.assertTrue(plan["key_matches_door"])
        self.assertEqual(plan["key_rotation_steps"], 0)
        self.assertEqual(plan["navigation"]["action"], "ACTION1")
        self.assertEqual(plan["target_center"], [36, 12])


if __name__ == "__main__":
    unittest.main()
