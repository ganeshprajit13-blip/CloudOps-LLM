# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# Deep Research RCA Agent - AgentCore Container
# Uses uv for fast dependency management

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Configure UV for container environment
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    DOCKER_CONTAINER=1 \
    OTEL_PYTHON_LOG_CORRELATION=true \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Install system dependencies for boto3 and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc=4:12.2.0-3 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY patterns/rca-deep-research/requirements.txt requirements.txt
RUN uv pip install --no-cache -r requirements.txt && \
    uv pip install --no-cache aws-opentelemetry-distro==0.16.0

# Create non-root user for security
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# Copy the RCA agent source code
COPY --chown=bedrock_agentcore:bedrock_agentcore src/ src/
COPY --chown=bedrock_agentcore:bedrock_agentcore scenarios/ scenarios/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping', timeout=2)" || exit 1

# Start agent with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "agentcore_app"]
