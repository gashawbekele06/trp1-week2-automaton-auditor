FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install minimal build deps for wheels and git for potential repo operations
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml pyproject.toml
COPY . /app

# Upgrade pip and install package (will build from pyproject)
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install --no-cache-dir .

# Default environment variables (can be overridden at runtime)
ENV LANGCHAIN_TRACING_V2=false

# Expose nothing specific; container runs CLI
CMD ["python", "src/graph.py", "--help"]
