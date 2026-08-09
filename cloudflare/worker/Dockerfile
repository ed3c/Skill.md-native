FROM docker.io/library/python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 10001 skill && mkdir -p /workspace && chown -R skill:skill /workspace
USER skill
WORKDIR /workspace
CMD ["sleep", "infinity"]
