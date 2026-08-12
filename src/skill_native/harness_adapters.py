from __future__ import annotations

from abc import ABC, abstractmethod
from string import Formatter

from .harness_contract import HarnessContractError, HarnessDomain, HarnessManifest
from .models import RunSpec


class DomainAdapter(ABC):
    adapter_id: str
    domain: HarnessDomain

    @abstractmethod
    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]: ...


class CodingCommandAdapter(DomainAdapter):
    adapter_id = "coding.command.v1"
    domain = HarnessDomain.CODING
    _formatter = Formatter()
    _allowed_fields = {"entrypoint", "run_id", "scenario_id", "task", "skill_digest"}

    def compile_command(self, manifest: HarnessManifest, spec: RunSpec) -> list[str]:
        context = {
            "entrypoint": spec.skill.entrypoint,
            "run_id": spec.run_id,
            "scenario_id": spec.scenario.id,
            "task": spec.scenario.task,
            "skill_digest": spec.skill.commit_or_digest,
        }
        return [self._render(value, context) for value in manifest.execution.command]

    def _render(self, value: str, context: dict[str, str]) -> str:
        for _, field_name, format_spec, conversion in self._formatter.parse(value):
            if field_name is None:
                continue
            if field_name not in self._allowed_fields:
                raise HarnessContractError(f"unsupported command placeholder: {field_name!r}")
            if format_spec or conversion:
                raise HarnessContractError(
                    "format specifiers and conversions are not allowed in command templates"
                )
        try:
            return value.format_map(context)
        except (KeyError, ValueError) as exc:
            raise HarnessContractError(f"invalid command template {value!r}") from exc


class DomainAdapterRegistry:
    def __init__(self, adapters: list[DomainAdapter] | None = None) -> None:
        self._adapters: dict[str, DomainAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: DomainAdapter) -> None:
        if not adapter.adapter_id:
            raise HarnessContractError("domain adapter id must not be empty")
        if adapter.adapter_id in self._adapters:
            raise HarnessContractError(f"duplicate domain adapter: {adapter.adapter_id}")
        self._adapters[adapter.adapter_id] = adapter

    def require(self, adapter_id: str) -> DomainAdapter:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise HarnessContractError(f"unknown domain adapter: {adapter_id}") from exc

    @classmethod
    def defaults(cls) -> "DomainAdapterRegistry":
        return cls([CodingCommandAdapter()])

