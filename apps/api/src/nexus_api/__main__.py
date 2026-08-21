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
import stat
import sys
import threading
import time
from typing import IO

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


def _shut_down(server: uvicorn.Server, reason: str) -> None:
    """Ask the server to stop, then make sure the process really goes away.

    Either watchdog can reach this, and whichever gets here first wins: the
    second call lands on a process that has already exited.
    """
    logger.warning("%s; shutting down sidecar", reason)
    server.should_exit = True
    time.sleep(SHUTDOWN_GRACE_SECONDS)
    os._exit(0)


def _watch_parent(server: uvicorn.Server, parent_pid: int) -> None:
    """Shut the sidecar down once the process that spawned it is gone.

    A force-quit of the shell would otherwise leave an orphaned sidecar holding
    the SQLite file, so the next launch fails for no visible reason. On POSIX an
    orphan is reparented, so the parent pid changing means the parent died.

    This watchdog is POSIX-only in effect: Windows does not reparent orphans, so
    the pid never changes there and this loop never ends. :func:`_watch_stdin`
    is what covers that platform.
    """
    while os.getppid() == parent_pid:
        time.sleep(PARENT_POLL_SECONDS)

    _shut_down(server, f"parent_process_exited pid={parent_pid}")


def _watch_stdin(server: uvicorn.Server) -> None:
    """Shut the sidecar down when the shell's end of the stdin pipe closes.

    The supervisor hands the sidecar a stdin pipe it never writes to. The
    operating system closes a dead process's pipe ends on every platform, so an
    EOF here means the shell is gone - and unlike :func:`_watch_parent`, that is
    true on Windows too, where an orphan keeps its original parent pid forever
    and the pid poll can never fire.

    Bytes that do arrive are discarded rather than treated as a shutdown: stdin
    carries no protocol, and only its closure is a signal.

    The watchdog arms itself only when stdin really is a pipe. A terminal, a
    ``/dev/null`` redirect, and a file all report EOF for reasons that have
    nothing to do with a dead parent, and treating those as one would stop a
    server the developer had just started by hand.
    """
    stream = sys.stdin
    if stream is None or not _is_pipe(stream):
        return

    try:
        buffer = stream.buffer
        while buffer.read(1):
            pass
    except (AttributeError, OSError, ValueError):
        # A stdin that errors is a stdin that is gone, which is the same signal.
        pass

    _shut_down(server, "stdin_closed")


def _is_pipe(stream: IO[str]) -> bool:
    """Whether this stream is one end of a pipe held open by another process.

    Node implements a ``'pipe'`` stdio slot with a socketpair on unix rather
    than a FIFO, and with a named pipe on Windows, so both shapes count.
    """
    try:
        mode = os.fstat(stream.fileno()).st_mode
    except (AttributeError, OSError, ValueError):
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)


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
    threading.Thread(
        target=_watch_stdin,
        args=(server,),
        name="stdin-watchdog",
        daemon=True,
    ).start()
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
