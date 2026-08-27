# Docker

## Purpose

Container definitions for local Nexus services.

## Local PostgreSQL

```bash
make dev-db
make db-migrate
```

Default connection (see root `.env.example`):

```text
postgresql+psycopg://nexus:nexus@localhost:5432/nexus
```

Compose file: `infra/docker/docker-compose.yml`.

## Firmware PlatformIO ESP32 image (Phase 15E)

```bash
docker build -t nexus-firmware-platformio-esp32:1.0.0 -f infra/docker/platformio-esp32/Dockerfile .
```

## Python Analysis image (Phase 16G)

Pinned scientific stack for offline `analysis.run` (network-none at runtime):

- Python 3.13
- numpy==2.2.3
- pandas==2.2.3
- matplotlib==3.10.0

```bash
docker build -t nexus-python-analysis:1.0.0 -f infra/docker/python-analysis/Dockerfile .
```

Then set:

```text
NEXUS_EXECUTION_RUNTIME=container
NEXUS_EXEC_CONTAINER_IMAGE=nexus-python-analysis:1.0.0
NEXUS_ANALYSIS_USE_STUB=0
```

## What belongs here

- Dockerfiles
- Compose files for local stacks

## What must not be placed here

- Application business logic
- Secrets
