import unittest

from tools.workflow_engine import WorkflowEngine, WorkflowError, demo_engine

class WorkflowEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = demo_engine()

    def test_composes_two_steps_and_passes_output(self):
        result = self.engine.run({"steps": [
            {"id": "clean", "capability": {"id": "text.normalize", "version": "1.0.0"},
             "args": {"text": "  hello   emoji   engine  "}},
            {"id": "count", "capability": {"id": "text.word_count", "version": "1.0.0"},
             "args": {"text": "$clean.text"}},
        ]})
        self.assertEqual(result["results"]["clean"]["text"], "hello emoji engine")
        self.assertEqual(result["results"]["count"]["count"], 3)
        self.assertEqual(len(result["trace"]), 2)

    def test_unknown_reference_fails_closed(self):
        with self.assertRaisesRegex(WorkflowError, "E_CAPABILITY_NOT_FOUND"):
            self.engine.run({"steps": [{"id": "x", "capability": {"id": "missing", "version": "1.0.0"}, "args": {}}]})

    def test_unverified_capability_cannot_execute(self):
        engine = WorkflowEngine({"capabilities": [
            {"id": "demo", "version": "1.0.0", "inputs": {}, "outputs": {},
             "permissions": [], "status": "planned"}]}, {"demo": lambda a: {}})
        with self.assertRaisesRegex(WorkflowError, "E_CAPABILITY_UNVERIFIED"):
            engine.run({"steps": [{"id": "x", "capability": {"id": "demo", "version": "1.0.0"}, "args": {}}]})

    def test_permission_required(self):
        engine = WorkflowEngine({"capabilities": [
            {"id": "demo", "version": "1.0.0", "inputs": {}, "outputs": {},
             "permissions": ["fs.read"], "status": "tested"}]}, {"demo": lambda a: {}}, set())
        with self.assertRaisesRegex(WorkflowError, "E_PERMISSION_DENIED"):
            engine.run({"steps": [{"id": "x", "capability": {"id": "demo", "version": "1.0.0"}, "args": {}}]})

    def test_input_type_checked(self):
        with self.assertRaisesRegex(WorkflowError, "E_INPUT_TYPE"):
            self.engine.run({"steps": [{"id": "x", "capability": {"id": "text.normalize", "version": "1.0.0"},
                                        "args": {"text": 123}}]})

if __name__ == "__main__":
    unittest.main()
