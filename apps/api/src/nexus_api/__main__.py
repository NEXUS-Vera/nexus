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
import os
import socket
import sys

import uvicorn

from .config import settings
from .main import app

HANDSHAKE_EVENT = "nexus.api.listening"
HANDSHAKE_SCHEMA_VERSION = "1.0.0"
LISTEN_BACKLOG = 2048


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


def main() -> None:
    sock = _bind_listening_socket(settings.host, settings.port)
    bound_host, bound_port = sock.getsockname()[:2]
    _announce(bound_host, bound_port)

    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="info"))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
