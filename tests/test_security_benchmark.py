import unittest

from skill_native.security_benchmark import builtin_cases, evaluate_cases


class SecurityBenchmarkTests(unittest.TestCase):
    def test_builtin_cases_have_perfect_expected_baseline(self):
        result = evaluate_cases(builtin_cases())
        self.assertEqual(result.total, 6)
        self.assertEqual(result.true_positive, 3)
        self.assertEqual(result.false_negative, 0)
        self.assertEqual(result.false_positive, 0)
        self.assertEqual(result.true_negative, 3)
        self.assertEqual(result.recall, 1.0)
        self.assertEqual(result.false_positive_rate, 0.0)

    def test_case_results_preserve_categories_and_rules(self):
        result = evaluate_cases(builtin_cases())
        by_id = {item["case_id"]: item for item in result.case_results}
        self.assertIn("undeclared_network", by_id["malicious-undeclared-network"]["finding_rules"])
        self.assertEqual(by_id["benign-workspace-write"]["security_gate"], "pass")


if __name__ == "__main__":
    unittest.main()
