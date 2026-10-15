# Nexus Python Analysis execution image (Phase 16G).
#
# Pre-installs a pinned scientific Python stack for offline analysis.run.
# Network is disabled at runtime; packages must exist in the image.
#
# Build:
#   docker build -t nexus-python-analysis:1.0.0 -f infra/docker/python-analysis/Dockerfile .
#
# Pin reference (build time):
#   Python 3.13 (base image)
#   numpy==2.2.3
#   pandas==2.2.3
#   matplotlib==3.10.0

FROM python:3.13-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libfreetype6 \
        libpng16-16 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir \
        "numpy==2.2.3" \
        "pandas==2.2.3" \
        "matplotlib==3.10.0" \
    && python3 -c "import numpy,pandas,matplotlib; print(numpy.__version__, pandas.__version__, matplotlib.__version__)" \
    && mkdir -p /workspace

WORKDIR /workspace

CMD ["python3", "--version"]
