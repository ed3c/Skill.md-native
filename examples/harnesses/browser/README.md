# Playwright Browser Harness loopback example

This fixture starts an operator-owned HTTP server on `127.0.0.1:8765` and runs a deterministic Chromium workflow through `browser.playwright.v1`.

It covers:

- action-plan delivery over stdin with a plan-bound digest;
- same-origin navigation policy;
- form fill and final-state text assertion;
- expected dialog, popup, and download handling;
- DOM, accessibility, screenshot, download, console, and network evidence;
- content-addressed artifacts;
- trusted receipt normalization and `HarnessVerdict` generation.

Install the optional dependency and Chromium:

```bash
python -m pip install -e '.[browser]'
python -m playwright install chromium
```

Run the complete fixture:

```bash
python examples/harnesses/browser/run_fixture.py
```

The fixture runtime intentionally uses backend `fake` and records:

```text
verification_state=deterministic-local-browser-integration
isolation=none
network_enforcement=playwright-origin-route-only
```

A passing result does not claim OpenShell/Cloudflare isolation, a public or credentialed website, visual/semantic agent planning, CAPTCHA handling, or production browser verification.
