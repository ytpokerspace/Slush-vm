import unittest
from arc3.belief_mcts import BeliefMCTS
from arc3.glyph_dsl import DEFAULT_PROGRAM, DSLParseError, parse_program, validate_program
from arc3.transition_learner import TransitionLearner
from arc3.world_model import WorldModel

class GlyphDslTests(unittest.TestCase):
    def test_default_program_parses(self):
        program = parse_program(DEFAULT_PROGRAM)
        validate_program(program)
        self.assertEqual(program.instructions[0].operation, "observe")
        self.assertEqual(program.instructions[-1].operation, "memorize")

    def test_act_requires_select(self):
        with self.assertRaises(DSLParseError):
            validate_program(parse_program("👁️ OBSERVE(frame)\n▶️ ACT(action)"))

class TransitionLearnerTests(unittest.TestCase):
    def test_exact_template_prediction(self):
        learner = TransitionLearner()
        before, after = {"frame": [[0, 1], [0, 0]]}, {"frame": [[0, 2], [0, 0]]}
        self.assertTrue(learner.observe({"name": "ACTION1"}, before, after))
        predictions = learner.predict({"name": "ACTION1"}, before)
        self.assertEqual(len(predictions), 1)
        self.assertEqual(predictions[0]["evidence"], "predicted_from_observed_template")
        self.assertEqual(predictions[0]["observation"]["frame"][0][1], 2)

    def test_precondition_mismatch(self):
        learner = TransitionLearner()
        learner.observe({"name": "ACTION1"}, {"frame": [[0, 1]]}, {"frame": [[0, 2]]})
        self.assertEqual(learner.predict({"name": "ACTION1"}, {"frame": [[0, 3]]}), [])

    def test_layered_frame_template(self):
        learner = TransitionLearner()
        before = {"frame": [[[0, 1]], [[2, 0]]]}
        after = {"frame": [[[0, 3]], [[2, 0]]]}
        self.assertTrue(learner.observe({"name": "ACTION1"}, before, after))
        prediction = learner.predict({"name": "ACTION1"}, before)
        self.assertEqual(prediction[0]["observation"]["frame"][0][0][1], 3)

class BeliefMctsTests(unittest.TestCase):
    def test_root_action_is_legal(self):
        world, obs = WorldModel(), {"frame": [[0, 1]]}
        legal = [{"name": "ACTION1"}, {"name": "ACTION2"}]
        world.observe(obs)
        world.register_legal_actions(obs, legal)
        result = BeliefMCTS(world, simulations=12, depth=2).search(obs, legal)
        self.assertIn(result["action"], legal)
        self.assertEqual(result["diagnostics"]["simulations"], 12)

    def test_empty_actions(self):
        result = BeliefMCTS(WorldModel()).search({}, [])
        self.assertIsNone(result["action"])
        self.assertEqual(result["status"], "no_legal_actions")

if __name__ == "__main__":
    unittest.main()
