import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

import httpx

from skill_native.github_ingest import GitHubIngestor, GitHubSkillSource


def archive_bytes(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            encoded = data.encode()
            info = tarfile.TarInfo(name=f"owner-repo-deadbeef/{name}")
            info.size = len(encoded)
            tf.addfile(info, io.BytesIO(encoded))
    return buf.getvalue()


class GitHubIngestTests(unittest.TestCase):
    def test_resolves_ref_and_builds_immutable_provenance(self):
        sha = "a" * 40
        archive = archive_bytes(
            {
                "skills/demo/SKILL.md": "---\nname: demo\n---\nDo the task.\n",
                "skills/demo/LICENSE": "MIT License\n",
                "skills/demo/requirements.txt": "httpx\n",
                "README.md": "ignore\n",
            }
        )

        def handler(request):
            if "/commits/main" in str(request.url):
                return httpx.Response(200, json={"sha": sha})
            if f"/tarball/{sha}" in str(request.url):
                return httpx.Response(200, content=archive)
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        source = GitHubSkillSource.from_url(
            "https://github.com/owner/repo",
            ref="main",
            skill_path="skills/demo",
        )
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as pd:
            result = GitHubIngestor(client=client).ingest(source, td, provenance_dir=pd)
            self.assertEqual(result.commit_sha, sha)
            self.assertTrue((Path(td) / "SKILL.md").is_file())
            self.assertEqual(result.provenance.attestations[0].immutable_ref, sha)
            self.assertEqual(result.provenance.license_expression, "MIT")
            self.assertIn("requirements.txt", result.provenance.dependency_files)
            self.assertEqual(len(result.provenance_digest), 64)
            self.assertIsNotNone(result.provenance_path)
            payload = json.loads(result.provenance_path.read_text())
            self.assertEqual(payload["content_sha256"], result.provenance.content_sha256)

    def test_missing_skill_path_fails(self):
        sha = "b" * 40
        archive = archive_bytes({"README.md": "nothing here"})

        def handler(request):
            if "/commits/main" in str(request.url):
                return httpx.Response(200, json={"sha": sha})
            return httpx.Response(200, content=archive)

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        source = GitHubSkillSource(owner="owner", repo="repo", ref="main", skill_path="skills/demo")
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                GitHubIngestor(client=client).ingest(source, td)

    def test_rejects_non_github_url(self):
        with self.assertRaises(ValueError):
            GitHubSkillSource.from_url("https://example.com/owner/repo", ref="main")


if __name__ == "__main__":
    unittest.main()
