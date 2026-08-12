# Coding Agent Harness deterministic fixture

This directory demonstrates the `coding.agent.v1` contract without a model,
credential, external network request, or live sandbox account.

Validate and compile the immutable plan:

```bash
skill-native validate-harness examples/harnesses/coding-agent/harness.yaml
skill-native plan-harness \
  examples/harnesses/coding-agent/harness.yaml \
  examples/harnesses/coding-agent/run.fake.yaml
```

The compiled command contains the trusted `skill-native-coding-runner`; the task
is supplied through standard input and represented in the plan only by its
SHA-256 digest. The child process cannot write the top-level receipt because its
stdout is captured inside the wrapper.

The executable end-to-end fixture is `tests/test_coding_agent.py`. It runs in a
temporary workspace and verifies version pinning, structured events, workspace
diff, protected paths, change budgets, deterministic tests, receipt integrity,
command continuity, input continuity, and the final Harness verdict.

A green fixture proves the local contract and evaluator implementation. It does
not prove that Codex, Gemini CLI, Qwen Code, OpenHands, OpenShell, or another
external runtime/model was exercised. Live runtime verification must preserve
the same receipt and evidence contract and be reported separately.
