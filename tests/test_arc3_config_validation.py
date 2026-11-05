"""Offline tests for Hyper Pipeline v3.3 configuration validation."""
from __future__ import annotations

import copy
import unittest

from arc3.config_validation import (
    DEFAULT_CONFIG,
    load_config,
    validate_config,
    validate_solver_compatibility,
)


class HyperPipelineConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(DEFAULT_CONFIG)

    def test_checked_in_profile_is_valid_and_matches_agent_defaults(self):
        self.assertEqual(validate_config(self.config), [])
        self.assertEqual(validate_solver_compatibility(self.config), [])

    def test_rejects_conflicting_fp8_and_awq_profile(self):
        config = copy.deepcopy(self.config)
        profile = config["model"]["profiles"]["research_server"]
        profile["precision"] = "fp8_e4m3"
        profile["quantization"] = "awq"
        self.assertTrue(any("FP8 weights and AWQ" in error for error in validate_config(config)))

    def test_rejects_live_benchmark_enablement(self):
        config = copy.deepcopy(self.config)
        config["evaluation"]["live_benchmark"]["enabled"] = True
        self.assertTrue(any("live ARC-AGI-3 benchmark" in error for error in validate_config(config)))

    def test_rejects_paid_or_network_execution(self):
        config = copy.deepcopy(self.config)
        config["execution_policy"]["paid_api_calls"] = True
        config["model"]["inference_constraints"]["network_required"] = True
        errors = validate_config(config)
        self.assertTrue(any("paid_api_calls" in error for error in errors))
        self.assertTrue(any("network_required" in error for error in errors))

    def test_rejects_invented_transitions_and_unsafe_actions(self):
        config = copy.deepcopy(self.config)
        config["arc_solver"]["world_model"]["invented_successors"] = True
        config["arc_solver"]["environment"]["legal_actions_only"] = False
        errors = validate_config(config)
        self.assertTrue(any("invented_successors" in error for error in errors))
        self.assertTrue(any("legal_actions_only" in error for error in errors))

    def test_rejects_mcts_limits_outside_runner_support(self):
        config = copy.deepcopy(self.config)
        config["arc_solver"]["mcts"]["default_depth"] = 7
        config["arc_solver"]["mcts"]["default_simulations"] = 513
        errors = validate_config(config)
        self.assertTrue(any("default_depth" in error for error in errors))
        self.assertTrue(any("default_simulations" in error for error in errors))

    def test_rejects_agent_default_drift(self):
        config = copy.deepcopy(self.config)
        config["arc_solver"]["mcts"]["default_depth"] = 2
        self.assertTrue(any("does not match" in error for error in validate_solver_compatibility(config)))

    def test_rejects_context_over_8k_in_consumer_profile(self):
        config = copy.deepcopy(self.config)
        config["model"]["profiles"]["consumer_local"]["max_context_tokens"] = 131072
        self.assertTrue(any("max_context_tokens" in error for error in validate_config(config)))


if __name__ == "__main__":
    unittest.main()
