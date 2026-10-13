import unittest
from tools.workflow_engine import EmojiResolver, WorkflowEngine, WorkflowError, demo_engine, load_json, ROOT

class WorkflowEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = demo_engine()

    def test_composes_emoji_steps_and_passes_output(self):
        workflow = load_json(ROOT / "examples" / "normalize_and_count.workflow.json")
        result = self.engine.run(workflow)
        self.assertEqual(result["results"]["clean"]["text"], "hello emoji engine")
        self.assertEqual(result["results"]["count"]["count"], 3)
        self.assertEqual([x["symbol"] for x in result["trace"]], ["🧹", "🧮"])
        self.assertEqual(len(result["trace"]), 2)

    def test_unknown_emoji_fails_closed(self):
        with self.assertRaisesRegex(WorkflowError, "E_ALIAS_NOT_FOUND"):
            self.engine.run({"steps": [{"id": "x", "symbol": "🦄", "namespace": "workflow", "args": {}}]})

    def test_vocabulary_symbol_without_workflow_alias_fails(self):
        with self.assertRaisesRegex(WorkflowError, "E_ALIAS_NOT_REGISTERED"):
            self.engine.run({"steps": [{"id": "x", "symbol": "📤", "namespace": "language", "args": {}}]})

    def test_emoji_requires_namespace(self):
        with self.assertRaisesRegex(WorkflowError, "E_NAMESPACE_REQUIRED"):
            self.engine.run({"steps": [{"id": "x", "symbol": "🧹", "args": {"text": "x"}}]})

    def test_alias_cannot_disagree_with_explicit_capability(self):
        with self.assertRaisesRegex(WorkflowError, "E_ALIAS_CONFLICT"):
            self.engine.run({"steps": [{"id": "x", "symbol": "🧹", "namespace": "workflow",
                                        "capability": {"id": "text.word_count", "version": "1.0.0"},
                                        "args": {"text": "x"}}]})

    def test_unknown_canonical_reference_fails_closed(self):
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

    def test_duplicate_aliases_fail_as_ambiguous(self):
        vocab = load_json(ROOT / "registry" / "vocabulary.json")
        aliases = load_json(ROOT / "registry" / "workflow_aliases.json")
        aliases["aliases"].append(dict(aliases["aliases"][0], capability_id="other.capability"))
        resolver = EmojiResolver(vocab, aliases)
        with self.assertRaisesRegex(WorkflowError, "E_ALIAS_AMBIGUOUS"):
            resolver.resolve("🧹", "workflow")

if __name__ == "__main__":
    unittest.main()
