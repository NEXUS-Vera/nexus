"""API configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "NEXUS_API_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    cors_origins: list[str]
    host: str = "127.0.0.1"
    port: int = 8000
    initialization_provider: str = "fixture"
    storage_backend: str = "memory"
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5432/nexus"
    model_provider: str = "openai"
    model_name: str = "gpt-4.1-mini"
    model_credential: str = ""
    model_base_url: str = "https://api.openai.com/v1"
    model_timeout_seconds: float = 60.0
    model_max_repair_attempts: int = 1
    wokwi_cli_executable: str = "wokwi-cli"
    wokwi_cli_token: str = ""
    wokwi_firmware_elf: str = ""
    file_store_root: str = ""
    workspace_max_file_bytes: int = 1_048_576
    workspace_max_bytes: int = 16_777_216
    workspace_max_file_count: int = 256
    execution_max_running_global: int = 2
    execution_max_running_per_project: int = 1
    execution_max_queued: int = 32
    execution_wall_time_ms: int = 30_000
    execution_stdout_bytes: int = 1_048_576
    execution_stderr_bytes: int = 1_048_576
    execution_total_log_bytes: int = 2_097_152
    execution_produced_output_bytes: int = 4_194_304
    execution_memory_bytes: int = 256 * 1024 * 1024
    execution_cpu_millis: int = 1000
    execution_process_count: int = 64
    execution_runtime: str = "process"
    execution_container_image: str = "python:3.13-slim"


def load_settings() -> Settings:
    return Settings(
        cors_origins=_cors_origins(),
        host=os.environ.get("NEXUS_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("NEXUS_API_PORT", "8000")),
        initialization_provider=os.environ.get("NEXUS_INITIALIZATION_PROVIDER", "fixture")
        .strip()
        .lower(),
        storage_backend=os.environ.get("NEXUS_STORAGE_BACKEND", "memory").strip().lower(),
        database_url=os.environ.get(
            "NEXUS_DATABASE_URL",
            "postgresql+psycopg://nexus:nexus@localhost:5432/nexus",
        ),
        model_provider=os.environ.get("NEXUS_MODEL_PROVIDER", "openai"),
        model_name=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        model_credential=os.environ.get("NEXUS_MODEL_API_KEY", ""),
        model_base_url=os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1"),
        model_timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "60")),
        model_max_repair_attempts=int(os.environ.get("NEXUS_MODEL_MAX_REPAIR_ATTEMPTS", "1")),
        wokwi_cli_executable=os.environ.get("NEXUS_WOKWI_CLI", "wokwi-cli"),
        wokwi_cli_token=os.environ.get("WOKWI_CLI_TOKEN", ""),
        wokwi_firmware_elf=os.environ.get("NEXUS_WOKWI_FIRMWARE_ELF", ""),
        file_store_root=os.environ.get("NEXUS_FILE_STORE_ROOT", "").strip(),
        workspace_max_file_bytes=int(os.environ.get("NEXUS_WORKSPACE_MAX_FILE_BYTES", "1048576")),
        workspace_max_bytes=int(os.environ.get("NEXUS_WORKSPACE_MAX_BYTES", "16777216")),
        workspace_max_file_count=int(os.environ.get("NEXUS_WORKSPACE_MAX_FILE_COUNT", "256")),
        execution_max_running_global=int(os.environ.get("NEXUS_EXEC_MAX_RUNNING_GLOBAL", "2")),
        execution_max_running_per_project=int(
            os.environ.get("NEXUS_EXEC_MAX_RUNNING_PER_PROJECT", "1")
        ),
        execution_max_queued=int(os.environ.get("NEXUS_EXEC_MAX_QUEUED", "32")),
        execution_wall_time_ms=int(os.environ.get("NEXUS_EXEC_WALL_TIME_MS", "30000")),
        execution_stdout_bytes=int(os.environ.get("NEXUS_EXEC_STDOUT_BYTES", "1048576")),
        execution_stderr_bytes=int(os.environ.get("NEXUS_EXEC_STDERR_BYTES", "1048576")),
        execution_total_log_bytes=int(os.environ.get("NEXUS_EXEC_TOTAL_LOG_BYTES", "2097152")),
        execution_produced_output_bytes=int(
            os.environ.get("NEXUS_EXEC_PRODUCED_OUTPUT_BYTES", "4194304")
        ),
        execution_memory_bytes=int(os.environ.get("NEXUS_EXEC_MEMORY_BYTES", str(256 * 1024 * 1024))),
        execution_cpu_millis=int(os.environ.get("NEXUS_EXEC_CPU_MILLIS", "1000")),
        execution_process_count=int(os.environ.get("NEXUS_EXEC_PROCESS_COUNT", "64")),
        execution_runtime=os.environ.get("NEXUS_EXECUTION_RUNTIME", "process").strip().lower(),
        execution_container_image=os.environ.get(
            "NEXUS_EXEC_CONTAINER_IMAGE", "python:3.13-slim"
        ).strip(),
    )


settings = load_settings()
