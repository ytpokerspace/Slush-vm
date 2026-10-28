import unittest

from arc3.object_perception import perceive_objects


class ObjectPerceptionTests(unittest.TestCase):
    def test_detects_shape_size_and_bounding_dimensions(self):
        result = perceive_objects({"grid": [
            [0, 0, 0, 0, 0, 0],
            [0, 2, 2, 0, 0, 0],
            [0, 2, 2, 0, 3, 0],
            [0, 0, 0, 0, 0, 0],
        ]}, max_height=None)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["object_count"], 2)
        square = next(o for o in result["objects"] if o["dominant_color"] == 2)
        self.assertEqual(square["shape"], "filled_square")
        self.assertEqual(square["area"], 4)
        self.assertEqual(square["bbox"]["width"], 2)
        self.assertEqual(square["bbox"]["height"], 2)
        self.assertEqual(square["relative_size"]["rank_by_area"], 1)

    def test_distinguishes_horizontal_and_vertical_lines(self):
        horizontal = perceive_objects({"grid": [[0, 0, 0], [4, 4, 4], [0, 0, 0]]}, max_height=None)
        self.assertEqual(horizontal["objects"][0]["shape"], "horizontal_line")
        vertical = perceive_objects({"grid": [[0, 5, 0], [0, 5, 0], [0, 5, 0]]}, max_height=None)
        self.assertEqual(vertical["objects"][0]["shape"], "vertical_line")

    def test_explicit_background_is_supported(self):
        result = perceive_objects({"grid": [[9, 1, 9], [9, 1, 9]]},
                                  background_colors=[9], max_height=None)
        self.assertEqual(result["object_count"], 1)
        self.assertEqual(result["objects"][0]["area"], 2)

    def test_invalid_observation_is_reported(self):
        self.assertEqual(perceive_objects(None)["status"], "insufficient_grid")

    def test_geometry_does_not_claim_semantic_identity(self):
        result = perceive_objects({"grid": [[0, 1, 0]]}, max_height=None)
        self.assertEqual(result["objects"][0]["identity_confidence"], 0.0)
        self.assertIn("possible_marker_or_moving_piece", result["objects"][0]["role_hypotheses"])


if __name__ == "__main__":
    unittest.main()
