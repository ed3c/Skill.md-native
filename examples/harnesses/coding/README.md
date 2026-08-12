# Coding Harness deterministic fixture

This directory is the first executable vertical slice of the cross-domain Harness Kernel:

```text
SKILL.md
+ harness.yaml
+ run.fake.yaml
+ FakeRuntime
+ EvidenceBundle
+ HarnessVerdict
```

Run it from the repository root:

```bash
skill-native validate-harness examples/harnesses/coding/harness.yaml
skill-native plan-harness \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml
skill-native run-harness-fake \
  examples/harnesses/coding/harness.yaml \
  examples/harnesses/coding/run.fake.yaml \
  --evidence-dir /tmp/skill-native-evidence \
  --verdict-dir /tmp/skill-native-verdicts
```

`FakeRuntime` is deterministic contract evidence only. It does not establish live sandbox, Coding Agent, model, network, filesystem, or credential-isolation behavior.
