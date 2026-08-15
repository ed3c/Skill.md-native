from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence import EvidenceStore
from .harness_kernel_impl import HarnessKernel as _HarnessKernel
from .harness_kernel_impl import HarnessVerdictStore


class _RuntimeCompatibilityProxy:
    """Preserve the pre-stdin RuntimeAdapter call contract.

    The core passes an explicit stdin keyword. Older third-party adapters only
    accept ``execute(sandbox_id, command)``. Calls without an input stream are
    delegated with that legacy signature; stdin-aware domains still require the
    extended method and fail closed when the runtime cannot provide it.
    """

    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def execute(
        self,
        sandbox_id: str,
        command: list[str],
        *,
        stdin: str | None = None,
    ) -> str:
        if stdin is None:
            return self._delegate.execute(sandbox_id, command)
        return self._delegate.execute(sandbox_id, command, stdin=stdin)


class HarnessKernel(_HarnessKernel):
    """Compatibility facade over the digest-addressed Harness Kernel."""

    @property
    def adapters(self) -> Any:
        """Read-only legacy alias for the current domain adapter registry."""

        return self.registry

    def run(self, manifest: Any, spec: Any, runtime: Any, **kwargs: Any) -> Any:
        evidence_dir = kwargs.pop("evidence_dir", None)
        verdict_dir = kwargs.pop("verdict_dir", None)
        if evidence_dir is not None:
            if kwargs.get("evidence_store") is not None:
                raise TypeError("pass either evidence_dir or evidence_store, not both")
            kwargs["evidence_store"] = EvidenceStore(Path(evidence_dir))
        if verdict_dir is not None:
            if kwargs.get("verdict_store") is not None:
                raise TypeError("pass either verdict_dir or verdict_store, not both")
            kwargs["verdict_store"] = HarnessVerdictStore(Path(verdict_dir))
        return super().run(
            manifest,
            spec,
            _RuntimeCompatibilityProxy(runtime),
            **kwargs,
        )


__all__ = ["HarnessKernel", "HarnessVerdictStore"]
