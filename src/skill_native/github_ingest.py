from __future__ import annotations

import io
import os
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

from .provenance import ProvenanceRecord, SourceAttestation, build_provenance


@dataclass(frozen=True)
class GitHubSkillSource:
    owner: str
    repo: str
    ref: str
    skill_path: str = "."
    entrypoint: str = "SKILL.md"

    @classmethod
    def from_url(cls, url: str, *, ref: str, skill_path: str = ".", entrypoint: str = "SKILL.md") -> "GitHubSkillSource":
        parsed = urlparse(url)
        if parsed.hostname != "github.com":
            raise ValueError("only github.com repository URLs are supported")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError("expected https://github.com/<owner>/<repo>")
        repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        return cls(owner=parts[0], repo=repo, ref=ref, skill_path=skill_path, entrypoint=entrypoint)


@dataclass(frozen=True)
class IngestedSkill:
    root: Path
    commit_sha: str
    provenance: ProvenanceRecord


class GitHubIngestor:
    """Resolve a GitHub ref to an immutable commit and materialize its Skill tree."""

    def __init__(self, client: httpx.Client | None = None, token_env: str = "GITHUB_TOKEN") -> None:
        self.client = client or httpx.Client(timeout=60.0, follow_redirects=True)
        self.token_env = token_env

    def ingest(self, source: GitHubSkillSource, destination: str | Path | None = None) -> IngestedSkill:
        headers = {"accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28"}
        token = os.getenv(self.token_env)
        if token:
            headers["authorization"] = f"Bearer {token}"

        commit_url = f"https://api.github.com/repos/{source.owner}/{source.repo}/commits/{source.ref}"
        commit_response = self.client.get(commit_url, headers=headers)
        commit_response.raise_for_status()
        commit_body = commit_response.json()
        commit_sha = commit_body.get("sha")
        if not isinstance(commit_sha, str) or len(commit_sha) < 40:
            raise RuntimeError("GitHub commit resolution did not return an immutable SHA")

        archive_url = f"https://api.github.com/repos/{source.owner}/{source.repo}/tarball/{commit_sha}"
        archive_response = self.client.get(archive_url, headers=headers)
        archive_response.raise_for_status()

        root = Path(destination) if destination else Path(tempfile.mkdtemp(prefix="skill-native-github-"))
        root.mkdir(parents=True, exist_ok=True)
        self._extract_skill_tree(archive_response.content, root, source.skill_path)

        entrypoint = root / source.entrypoint
        if not entrypoint.is_file():
            raise FileNotFoundError(f"Skill entrypoint not found: {source.entrypoint}")

        attestation = SourceAttestation(
            registry="github",
            source_url=f"https://github.com/{source.owner}/{source.repo}",
            immutable_ref=commit_sha,
            publisher=source.owner,
        )
        provenance = build_provenance(root, entrypoint=source.entrypoint, attestation=attestation)
        return IngestedSkill(root=root, commit_sha=commit_sha, provenance=provenance)

    @staticmethod
    def _extract_skill_tree(archive: bytes, destination: Path, skill_path: str) -> None:
        requested = PurePosixPath(skill_path.strip("/")) if skill_path not in {"", "."} else PurePosixPath(".")
        extracted = 0
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            if not members:
                raise RuntimeError("GitHub archive is empty")
            top = PurePosixPath(members[0].name).parts[0]
            for member in members:
                path = PurePosixPath(member.name)
                parts = path.parts
                if not parts or parts[0] != top:
                    continue
                relative = PurePosixPath(*parts[1:])
                if requested != PurePosixPath("."):
                    try:
                        relative = relative.relative_to(requested)
                    except ValueError:
                        continue
                if not relative.parts or ".." in relative.parts:
                    continue
                target = destination.joinpath(*relative.parts)
                resolved = target.resolve()
                if destination.resolve() not in resolved.parents and resolved != destination.resolve():
                    raise RuntimeError("archive path escapes destination")
                target.parent.mkdir(parents=True, exist_ok=True)
                fileobj = tf.extractfile(member)
                if fileobj is None:
                    continue
                target.write_bytes(fileobj.read())
                extracted += 1
        if extracted == 0:
            raise FileNotFoundError(f"Skill path not found in repository archive: {skill_path}")
