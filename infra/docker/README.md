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

## What belongs here

- Dockerfiles
- Compose files for local stacks

## What must not be placed here

- Application business logic
- Secrets
