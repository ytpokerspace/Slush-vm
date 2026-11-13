import unittest

from arc3.egp_runtime import EGPEnvironmentRuntime


class FakeAction:
    def __init__(self, name, complex_action=False):
        self.name = name
        self._complex = complex_action

    def is_complex(self):
        return self._complex


class FakeEnvironment:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def step(self, action, data=None):
        self.calls.append((action, data))
        return self.result


class EGPEnvironmentRuntimeTests(unittest.TestCase):
    def test_executes_only_current_legal_action(self):
        action = FakeAction("ACTION1")
        env = FakeEnvironment({"frame": [[1]]})
        runtime = EGPEnvironmentRuntime(env)

        result = runtime.act([action], action, {"name": "ACTION1"})

        self.assertEqual(result, {"frame": [[1]]})
        self.assertEqual(env.calls, [(action, None)])
        self.assertEqual(runtime.snapshot()["actions_executed"], 1)
        self.assertEqual(runtime.last_trace["glyph"], "▶️")

    def test_rejects_action_outside_legal_action_space(self):
        legal = FakeAction("ACTION1")
        illegal = FakeAction("ACTION2")
        env = FakeEnvironment()
        runtime = EGPEnvironmentRuntime(env)

        with self.assertRaises(ValueError):
            runtime.act([legal], illegal, {"name": "ACTION2"})
        self.assertEqual(env.calls, [])

    def test_complex_action_uses_candidate_payload(self):
        action = FakeAction("CLICK", complex_action=True)
        env = FakeEnvironment("next-frame")
        runtime = EGPEnvironmentRuntime(env)

        result = runtime.act(
            [action], action, {"name": "CLICK", "data": {"x": 7, "y": 9}}
        )

        self.assertEqual(result, "next-frame")
        self.assertEqual(env.calls, [(action, {"x": 7, "y": 9})])

    def test_complex_action_requires_payload_or_explicit_fallback(self):
        action = FakeAction("CLICK", complex_action=True)
        env = FakeEnvironment()
        runtime = EGPEnvironmentRuntime(env)

        with self.assertRaises(ValueError):
            runtime.act([action], action, {"name": "CLICK"})
        self.assertEqual(env.calls, [])

    def test_rejects_record_action_name_mismatch(self):
        action = FakeAction("ACTION1")
        env = FakeEnvironment()
        runtime = EGPEnvironmentRuntime(env)

        with self.assertRaises(ValueError):
            runtime.act([action], action, {"name": "ACTION2"})
        self.assertEqual(env.calls, [])


if __name__ == "__main__":
    unittest.main()
