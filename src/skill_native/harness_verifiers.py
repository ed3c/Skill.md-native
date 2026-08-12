from __future__ import annotations

from .evidence import captured_evidence
from .harness_contract import (
    AssertionTrueVerifier,
    EvidenceKind,
    EvidencePresentVerifier,
    ExitCodeZeroVerifier,
    HarnessContractError,
    StderrEmptyVerifier,
    StdoutContainsVerifier,
    VerificationResult,
    VerifierSpec,
)
from .models import EvidenceBundle


def evaluate_verifier(
    verifier: VerifierSpec, evidence: EvidenceBundle
) -> VerificationResult:
    if isinstance(verifier, ExitCodeZeroVerifier):
        passed = evidence.exit_code == 0
        return VerificationResult(
            id=verifier.id,
            kind=verifier.kind,
            passed=passed,
            message=f"exit_code={evidence.exit_code!r}",
            details={"exit_code": evidence.exit_code},
        )
    if isinstance(verifier, AssertionTrueVerifier):
        value = evidence.assertions.get(verifier.assertion)
        passed = value is True
        return VerificationResult(
            id=verifier.id,
            kind=verifier.kind,
            passed=passed,
            message=f"assertion {verifier.assertion!r} is {value!r}",
            details={"assertion": verifier.assertion, "value": value},
        )
    if isinstance(verifier, StdoutContainsVerifier):
        passed = verifier.value in evidence.stdout
        return VerificationResult(
            id=verifier.id,
            kind=verifier.kind,
            passed=passed,
            message=(
                f"stdout contains {verifier.value!r}"
                if passed
                else f"stdout does not contain {verifier.value!r}"
            ),
            details={"value": verifier.value},
        )
    if isinstance(verifier, StderrEmptyVerifier):
        captured = evidence_present(evidence, EvidenceKind.STDERR)
        passed = captured and evidence.stderr == ""
        return VerificationResult(
            id=verifier.id,
            kind=verifier.kind,
            passed=passed,
            message=(
                "stderr was captured and is empty"
                if passed
                else "stderr is not empty or was not captured"
            ),
        )
    if isinstance(verifier, EvidencePresentVerifier):
        passed = evidence_present(evidence, verifier.evidence)
        return VerificationResult(
            id=verifier.id,
            kind=verifier.kind,
            passed=passed,
            message=(
                f"evidence {verifier.evidence.value!r} is present"
                if passed
                else f"evidence {verifier.evidence.value!r} is missing"
            ),
            details={"evidence": verifier.evidence.value},
        )
    raise HarnessContractError(f"unsupported verifier type: {type(verifier).__name__}")


def evidence_present(evidence: EvidenceBundle, kind: EvidenceKind) -> bool:
    if kind.value in captured_evidence(evidence):
        return True
    value = getattr(evidence, kind.value)
    if kind is EvidenceKind.EXIT_CODE:
        return value is not None
    if kind in {EvidenceKind.STDOUT, EvidenceKind.STDERR}:
        return bool(value)
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None

