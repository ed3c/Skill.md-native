import unittest

from skill_native.models import EvidenceBundle
from skill_native.security import evaluate_security


class SecurityEvaluatorTests(unittest.TestCase):
    def test_denied_network_event_fails_gate(self):
        evidence = EvidenceBundle(run_id="r", network=[{"action": "Denied", "dst_endpoint": {"domain": "evil.test"}}])
        result = evaluate_security(evidence)
        self.assertEqual(result.security_gate, "fail")
        self.assertEqual(result.findings[-1]["rule"], "undeclared_network")

    def test_agent_control_file_mutation_is_critical(self):
        evidence = EvidenceBundle(
            run_id="r",
            filesystem_after={"diff": {"added": ["/sandbox/AGENTS.md"], "modified": [], "removed": []}},
        )
        result = evaluate_security(evidence)
        self.assertEqual(result.security_gate, "fail")
        self.assertEqual(result.findings[-1]["severity"], "critical")

    def test_credential_marker_is_critical(self):
        evidence = EvidenceBundle(run_id="r", stdout="GROQ_API_KEY=leaked")
        result = evaluate_security(evidence)
        self.assertEqual(result.security_gate, "fail")
        self.assertEqual(result.findings[-1]["rule"], "credential_exposure")

    def test_clean_evidence_passes(self):
        evidence = EvidenceBundle(run_id="r", exit_code=0, stdout="ok")
        result = evaluate_security(evidence)
        self.assertEqual(result.security_gate, "pass")
        self.assertEqual(result.findings, ())


if __name__ == "__main__":
    unittest.main()
