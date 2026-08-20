"""Sidecar entrypoint: bind a socket, announce it, then serve on it.

The desktop shell spawns this module as a child process. Because a fixed port
collides with the user's own tooling and with other users on a shared machine,
the sidecar binds the port the operating system gives it and announces the
result on stdout.

Handshake contract (stdout, exactly one line, terminated by ``\\n``):

```json
{"event":"nexus.api.listening","schemaVersion":"1.0.0","host":"127.0.0.1","port":54321,"pid":4242}
```

The line is emitted after the socket is bound and listening, so a connection
made the instant the supervisor reads it is accepted rather than refused.
stdout carries nothing but this contract; all logging goes to stderr.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
import threading
import time

import uvicorn

from .config import settings
from .main import app

logger = logging.getLogger("nexus.api.sidecar")

HANDSHAKE_EVENT = "nexus.api.listening"
HANDSHAKE_SCHEMA_VERSION = "1.0.0"
LISTEN_BACKLOG = 2048
PARENT_POLL_SECONDS = 0.25
SHUTDOWN_GRACE_SECONDS = 5.0


def _bind_listening_socket(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(LISTEN_BACKLOG)
    return sock


def _announce(host: str, port: int) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "event": HANDSHAKE_EVENT,
                "schemaVersion": HANDSHAKE_SCHEMA_VERSION,
                "host": host,
                "port": port,
                "pid": os.getpid(),
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()


def _watch_parent(server: uvicorn.Server, parent_pid: int) -> None:
    """Shut the sidecar down once the process that spawned it is gone.

    A force-quit of the shell would otherwise leave an orphaned sidecar holding
    the SQLite file, so the next launch fails for no visible reason. On POSIX an
    orphan is reparented, so the parent pid changing means the parent died.
    """
    while os.getppid() == parent_pid:
        time.sleep(PARENT_POLL_SECONDS)

    logger.warning("parent_process_exited pid=%s; shutting down sidecar", parent_pid)
    server.should_exit = True
    time.sleep(SHUTDOWN_GRACE_SECONDS)
    os._exit(0)


def main() -> None:
    sock = _bind_listening_socket(settings.host, settings.port)
    bound_host, bound_port = sock.getsockname()[:2]
    _announce(bound_host, bound_port)

    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="info"))
    threading.Thread(
        target=_watch_parent,
        args=(server, os.getppid()),
        name="parent-watchdog",
        daemon=True,
    ).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
