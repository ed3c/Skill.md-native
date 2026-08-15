#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="${SKILL_NATIVE_AUDIT_OUTPUT:-${ROOT}/.skill-native/capability-audit}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV="${SKILL_NATIVE_AUDIT_VENV:-${ROOT}/.venv-capability-audit}"

if [[ "${SKILL_NATIVE_AUDIT_BOOTSTRAP:-1}" == "1" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV}"
  "${VENV}/bin/python" -m pip install --upgrade pip
  (
    cd "${ROOT}"
    "${VENV}/bin/python" -m pip install -e '.[browser]'
  )
  "${VENV}/bin/python" -m playwright install chromium
  PYTHON_BIN="${VENV}/bin/python"
fi

exec "${PYTHON_BIN}" "${ROOT}/audit/run.py" \
  --output "${OUTPUT}" \
  --clean \
  --full \
  "$@"
