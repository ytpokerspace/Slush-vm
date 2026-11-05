import unittest
from arc3.memory_partition import MemoryItem, partition_memory, trace_decision

class MemoryPartitionTests(unittest.TestCase):
    def test_relevant_memories_are_prioritized(self):
        items = [MemoryItem('a', 'ARC search action model', token_cost=10), MemoryItem('b', 'unrelated cooking notes', token_cost=10)]
        plan = partition_memory('ARC search', items, token_budget=100)
        self.assertIn('a', plan.primary_ids)
        self.assertIn('b', plan.archive_ids)

    def test_budget_is_bounded(self):
        items = [MemoryItem(str(i), 'ARC search planning', token_cost=10) for i in range(20)]
        plan = partition_memory('ARC search planning', items, token_budget=50, side_task_share=0.2)
        self.assertLessEqual(plan.estimated_tokens, 50)

    def test_trace_is_compact_and_labeled(self):
        trace = trace_decision('task', 'ACTION1', ['frame changed'], ['ACTION2'], ['mem-1'], 0.7)
        self.assertEqual(trace['trace_type'], 'concise_decision_record')

if __name__ == '__main__':
    unittest.main()
