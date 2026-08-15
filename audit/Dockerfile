ARG PYTHON_IMAGE=python:3.11.15-slim-bookworm
FROM ${PYTHON_IMAGE}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir .

COPY examples ./examples
COPY schemas ./schemas

LABEL org.opencontainers.image.source="https://github.com/ed3c/Skill.md-native" \
      org.opencontainers.image.description="Skill.md-native capability-audit runtime image"

ENTRYPOINT ["skill-native"]
