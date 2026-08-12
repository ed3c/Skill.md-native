# Run Artifact Bundle deterministic fixture

This fixture contains one internally consistent authority/plan/evidence/verdict chain for the standalone Run Artifact builder.

It uses synthetic digests and a no-model `fake` runtime identity. It proves schema, digest, graph, replay, trace, scorecard, and persistence behavior only. It is not live model or isolated-runtime evidence.

```bash
skill-native-run-artifacts build \
  --authority examples/run-artifacts/authority.json \
  --plan examples/run-artifacts/plan.json \
  --evidence examples/run-artifacts/evidence.json \
  --verdict examples/run-artifacts/verdict.json \
  --output /tmp/run-artifacts
```

Expected properties:

- authority is immutable and binds the plan manifest digest;
- mandatory evidence is explicitly collector-attested;
- security gate and all verifier checks pass;
- runtime image is SHA-256 pinned;
- replay remains `partial` because no runtime snapshot was captured;
- scorecard is rank eligible;
- trace timing state is `not-captured`;
- six content-addressed JSON artifacts are persisted.
