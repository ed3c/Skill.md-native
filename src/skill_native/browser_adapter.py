from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any

from .browser_contract import (
    BrowserArtifact,
    BrowserContract,
    BrowserContractError,
    build_browser_runner_config,
    browser_action_plan_digest,
    browser_contract_digest,
    parse_browser_receipt,
)
from .evidence import canonical_digest, mark_evidence_captured
from .harness_contract import (
    HarnessContractError,
    HarnessDomain,
    HarnessManifest,
    HarnessPlan,
    VerificationResult,
)
from .models import EvidenceBundle, RunSpec


class BrowserPlaywrightAdapter:
    adapter_id = "browser.playwright.v1"
    domain = HarnessDomain.BROWSER
    runner_binary = "skill-native-browser-runner"
    evidence_kinds = frozenset(
        {
            "network",
            "browser_receipt",
            "browser_events",
            "dom_snapshot",
            "accessibility_snapshot",
            "network_trace",
            "screenshots",
            "downloads",
            "browser_assertions",
        }
    )
    receipt_evidence_kinds = frozenset(
        {
            "network",
            "browser_receipt",
            "browser_events",
            "network_trace",
            "browser_assertions",
        }
    )

    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]:
        self._contract(manifest)
        return [self.runner_binary, "--config-stdin"]

    def compile_stdin(self, manifest: HarnessManifest, spec: RunSpec) -> str:
        config = build_browser_runner_config(
            run_id=spec.run_id,
            contract=self._contract(manifest),
        )
        return json.dumps(
            config.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )

    def normalize_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> EvidenceBundle:
        assertions = dict(evidence.assertions)
        metadata = dict(evidence.runtime_metadata)
        try:
            contract = self._contract(manifest)
            receipt = parse_browser_receipt(evidence.stdout)
            config = build_browser_runner_config(
                run_id=plan.run_id,
                contract=contract,
            )
            expected_stdin = json.dumps(
                config.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            )
            expected_stdin_digest = hashlib.sha256(
                expected_stdin.encode("utf-8")
            ).hexdigest()
            mismatches: list[str] = []
            if receipt.run_id != plan.run_id:
                mismatches.append("run_id")
            if receipt.config_digest != config.config_digest:
                mismatches.append("config_digest")
            if receipt.contract_digest != browser_contract_digest(contract):
                mismatches.append("contract_digest")
            if receipt.action_plan_digest != browser_action_plan_digest(
                contract.actions
            ):
                mismatches.append("action_plan_digest")
            if plan.stdin_digest != expected_stdin_digest:
                mismatches.append("stdin_digest")
            if receipt.driver != contract.driver:
                mismatches.append("driver")
            if receipt.driver_version != contract.driver_version:
                mismatches.append("driver_version")
            if receipt.browser != contract.browser:
                mismatches.append("browser")
            if receipt.headless is not contract.headless:
                mismatches.append("headless")
            if receipt.page_count > contract.max_pages:
                mismatches.append("page_count")
            if len(receipt.events) > contract.max_events:
                mismatches.append("events")
            if len(receipt.network_events) > contract.max_network_events:
                mismatches.append("network_events")
            if mismatches:
                raise BrowserContractError(
                    "browser receipt does not preserve the compiled plan: "
                    + ", ".join(mismatches)
                )

            normalized_network = []
            for index, event in enumerate(receipt.network_events):
                payload = {"sequence": index, **event}
                normalized_network.append(
                    {**payload, "evidence_id": canonical_digest(payload)}
                )

            artifacts_by_kind: dict[str, list[dict[str, Any]]] = {}
            for artifact in receipt.artifacts:
                artifacts_by_kind.setdefault(artifact.kind, []).append(
                    artifact.model_dump(mode="json")
                )
        except Exception as exc:  # noqa: BLE001 - malformed runner output becomes evidence
            assertions.update(
                {
                    "browser_receipt_valid": False,
                    "browser_outcome_pass": False,
                    "browser_policy_pass": False,
                    "browser_artifacts_valid": False,
                    "browser_wrapper_exit_consistent": False,
                }
            )
            metadata["browser"] = {
                "receipt_valid": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
            return evidence.model_copy(
                update={"assertions": assertions, "runtime_metadata": metadata}
            )

        artifact_error: str | None = None
        artifact_root: Path | None = None
        total_artifact_bytes = 0
        try:
            artifact_root, total_artifact_bytes = _validate_artifacts(
                contract,
                plan.run_id,
                receipt.artifacts,
                evidence.runtime_metadata,
                require_complete=receipt.outcome == "pass",
            )
        except Exception as exc:  # preserve bound failure evidence; fail the artifact gate
            artifact_error = f"{type(exc).__name__}: {exc}"

        if artifact_error is None:
            dom_snapshot = _single_artifact(artifacts_by_kind.get("dom", []))
            accessibility_snapshot = _single_artifact(
                artifacts_by_kind.get("aria", [])
            )
            screenshots = artifacts_by_kind.get("screenshot", [])
            downloads = artifacts_by_kind.get("download", [])
        else:
            dom_snapshot = {}
            accessibility_snapshot = {}
            screenshots = []
            downloads = []

        wrapper_exit_consistent = (receipt.outcome == "pass") == (
            evidence.exit_code == 0
        )
        assertions.update(
            {
                "browser_receipt_valid": True,
                "browser_outcome_pass": receipt.outcome == "pass",
                "browser_policy_pass": (
                    all(receipt.policy_checks.values()) and not receipt.violations
                ),
                "browser_artifacts_valid": artifact_error is None,
                "browser_wrapper_exit_consistent": wrapper_exit_consistent,
                "browser_driver_verified": (
                    receipt.driver_version == contract.driver_version
                ),
                "browser_assertions_passed": all(receipt.assertions.values()),
            }
        )
        metadata["browser"] = {
            "receipt_valid": True,
            "receipt_digest": receipt.receipt_digest,
            "runner_version": receipt.runner_version,
            "driver": receipt.driver,
            "driver_version": receipt.driver_version,
            "browser": receipt.browser,
            "browser_version": receipt.browser_version,
            "headless": receipt.headless,
            "outcome": receipt.outcome,
            "final_url": receipt.final_url,
            "page_count": receipt.page_count,
            "artifact_root": str(artifact_root) if artifact_root is not None else None,
            "artifact_bytes": total_artifact_bytes,
            "artifact_validation_error": artifact_error,
        }
        normalized = evidence.model_copy(
            update={
                "assertions": assertions,
                "runtime_metadata": metadata,
                "network": normalized_network,
                "browser_receipt": receipt.model_dump(mode="json"),
                "browser_events": [
                    event.model_dump(mode="json") for event in receipt.events
                ],
                "dom_snapshot": dom_snapshot,
                "accessibility_snapshot": accessibility_snapshot,
                "network_trace": list(receipt.network_events),
                "screenshots": screenshots,
                "downloads": downloads,
                "browser_assertions": dict(receipt.assertions),
            }
        )
        captured = set(self.receipt_evidence_kinds)
        if artifact_error is None:
            if dom_snapshot:
                captured.add("dom_snapshot")
            if accessibility_snapshot:
                captured.add("accessibility_snapshot")
            if screenshots:
                captured.add("screenshots")
            if downloads:
                captured.add("downloads")
        return mark_evidence_captured(normalized, captured)

    def verify_evidence(
        self,
        manifest: HarnessManifest,
        plan: HarnessPlan,
        evidence: EvidenceBundle,
    ) -> list[VerificationResult]:
        checks = [
            (
                "domain:browser-receipt-continuity",
                "browser_receipt_valid",
                "browser receipt is valid and preserves the compiled plan",
            ),
            (
                "domain:browser-outcome",
                "browser_outcome_pass",
                "browser actions and final assertions passed",
            ),
            (
                "domain:browser-policy",
                "browser_policy_pass",
                "origin, page, event, artifact, and side-effect policies passed",
            ),
            (
                "domain:browser-artifacts",
                "browser_artifacts_valid",
                "browser artifacts remain inside the trusted root and match their digests",
            ),
            (
                "domain:browser-wrapper-exit",
                "browser_wrapper_exit_consistent",
                "wrapper exit status is consistent with the browser receipt",
            ),
        ]
        return [
            VerificationResult(
                id=check_id,
                kind="browser_playwright",
                passed=evidence.assertions.get(assertion) is True,
                message=(
                    message
                    if evidence.assertions.get(assertion) is True
                    else f"{message} — failed"
                ),
                details={"assertion": assertion},
            )
            for check_id, assertion, message in checks
        ]

    @staticmethod
    def _contract(manifest: HarnessManifest) -> BrowserContract:
        if manifest.browser is None:
            raise HarnessContractError(
                "browser.playwright.v1 requires a browser contract"
            )
        return manifest.browser


def _validate_artifacts(
    contract: BrowserContract,
    run_id: str,
    artifacts: list[BrowserArtifact],
    runtime_metadata: dict[str, Any],
    *,
    require_complete: bool,
) -> tuple[Path, int]:
    workspace_value = runtime_metadata.get("workspace_root")
    if not isinstance(workspace_value, str) or not workspace_value:
        raise BrowserContractError(
            "browser artifact verification requires trusted workspace_root metadata"
        )
    workspace = Path(workspace_value).resolve()
    root = (workspace / contract.artifact_root / run_id).resolve()
    try:
        root.relative_to(workspace)
    except ValueError as exc:
        raise BrowserContractError("browser artifact root escapes workspace") from exc
    if not root.is_dir() or root.is_symlink():
        raise BrowserContractError("browser artifact root is missing or unsafe")
    total = 0
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.path in seen:
            raise BrowserContractError(
                "browser receipt contains duplicate artifact paths"
            )
        seen.add(artifact.path)
        path = (root / artifact.path).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BrowserContractError("browser artifact escapes trusted root") from exc
        info = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(info.st_mode):
            raise BrowserContractError("browser artifact is not a regular file")
        if info.st_size != artifact.bytes:
            raise BrowserContractError(
                "browser artifact size does not match receipt"
            )
        if _file_digest(path) != artifact.sha256:
            raise BrowserContractError(
                "browser artifact digest does not match receipt"
            )
        if (
            artifact.kind == "download"
            and artifact.bytes > contract.max_download_bytes
        ):
            raise BrowserContractError("browser download exceeds byte budget")
        total += artifact.bytes
    if total > contract.max_artifact_bytes:
        raise BrowserContractError("browser artifacts exceed total byte budget")
    if (
        require_complete
        and contract.capture_dom
        and not any(value.kind == "dom" for value in artifacts)
    ):
        raise BrowserContractError("browser receipt is missing mandatory DOM artifact")
    if (
        require_complete
        and contract.capture_aria
        and not any(value.kind == "aria" for value in artifacts)
    ):
        raise BrowserContractError("browser receipt is missing mandatory ARIA artifact")
    if (
        require_complete
        and contract.final_screenshot
        and not any(value.kind == "screenshot" for value in artifacts)
    ):
        raise BrowserContractError(
            "browser receipt is missing mandatory screenshot"
        )
    return root, total


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _single_artifact(values: list[dict[str, Any]]) -> dict[str, Any]:
    if len(values) > 1:
        raise BrowserContractError(
            "browser receipt contains duplicate singular artifacts"
        )
    return values[0] if values else {}


__all__ = ["BrowserPlaywrightAdapter"]
