import unittest

from arc3.object_perception import perceive_objects
from arc3.object_tracker import update_object_tracks


class ObjectTrackerTests(unittest.TestCase):
    def test_unknown_identity_is_preserved_as_a_track_variable(self):
        perception = perceive_objects({"grid": [[0, 2, 2, 0]]}, max_height=None)
        state = update_object_tracks(None, perception)
        track = state["tracks"][0]
        self.assertEqual(track["identity_status"], "undetermined")
        self.assertEqual(track["identity_hypotheses"], [])
        self.assertEqual(track["identity_confidence"], 0.0)
        self.assertIn("track_id", track)
        self.assertIn("relevance", track)

    def test_track_persists_when_object_moves(self):
        first = perceive_objects({"grid": [[0, 2, 2, 0, 0]]}, max_height=None)
        state1 = update_object_tracks(None, first)
        first_id = state1["tracks"][0]["track_id"]
        second = perceive_objects({"grid": [[0, 0, 2, 2, 0]]}, max_height=None)
        state2 = update_object_tracks(state1, second, max_distance=4)
        self.assertEqual(state2["tracks"][0]["track_id"], first_id)
        self.assertEqual(state2["tracks"][0]["motion_delta"], [1.0, 0.0])

    def test_temporarily_missing_track_is_retained_then_expires(self):
        seen = perceive_objects({"grid": [[0, 3, 0]]}, max_height=None)
        state1 = update_object_tracks(None, seen, max_missed=1)
        empty = {"status": "ok", "objects": []}
        state2 = update_object_tracks(state1, empty, max_missed=1)
        self.assertEqual(state2["retained_unobserved_track_ids"], [state1["tracks"][0]["track_id"]])
        state3 = update_object_tracks(state2, empty, max_missed=1)
        self.assertEqual(state3["tracks"], [])

    def test_relevance_score_is_explicitly_not_probability(self):
        perception = perceive_objects({"grid": [[0, 1, 1, 0]]}, max_height=None)
        track = update_object_tracks(None, perception)["tracks"][0]
        self.assertEqual(track["relevance"]["score_type"], "heuristic_salience_not_probability")
        self.assertGreaterEqual(track["relevance"]["score"], 0.0)
        self.assertLessEqual(track["relevance"]["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
