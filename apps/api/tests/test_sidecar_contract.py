"""Loopback sidecar hardening tests (issue #43).

These exercise the public HTTP/process surface the Electron shell will drive:
session-token auth, the stdout port handshake, and parent-death lifecycle.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from nexus_api.config import DEV_SESSION_TOKEN, settings
from nexus_api.main import app

SIDECAR_TOKEN = "test-session-token"


@pytest.mark.asyncio
async def test_request_without_session_token_is_401() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/projects/proj_abcdefghijklmnop")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"


@pytest.mark.asyncio
async def test_non_ascii_credential_is_rejected_not_crashed() -> None:
    """A byte above 0x7F in the header must still produce the documented 401.

    Starlette decodes headers as latin-1, so such a byte arrives as a non-ASCII
    ``str`` - and ``secrets.compare_digest`` raises ``TypeError`` rather than
    returning ``False`` for those. Unhandled, that surfaces as a 500 with a
    stack trace where an authentication failure belongs.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/projects/proj_abcdefghijklmnop",
            # Raw bytes, because that is what a client puts on the wire; letting
            # httpx encode a str would fail here rather than at the server.
            headers=[(b"authorization", b"Bearer \xff\xfe")],
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"


@pytest.mark.asyncio
async def test_401_is_readable_by_the_browser_that_asked() -> None:
    """The rejection has to carry CORS headers, or the browser hides it.

    The token check and CORS are both middleware, and only the outermost one
    decorates a response the inner one short-circuits. With the token check on
    the outside, a 401 comes back with no ``Access-Control-Allow-Origin``; the
    browser then blocks the body and ``fetch`` rejects, so the renderer reports
    a network failure for what was really an expired credential.
    """
    origin = settings.cors_origins[0]
    if origin == "*":
        origin = "http://localhost:5173"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/projects/proj_abcdefghijklmnop",
            headers={"Origin": origin, "Authorization": "Bearer not-the-token"},
        )

    assert response.status_code == 401
    assert response.headers.get("access-control-allow-origin") is not None


@pytest.mark.asyncio
async def test_preflight_shaped_request_without_an_origin_is_still_rejected() -> None:
    """No route is reachable without the token, preflight-looking or not.

    A real browser preflight always carries an ``Origin`` and is answered by
    ``CORSMiddleware`` outside this check, so it never reaches the token
    middleware at all. A request that only looks like one - the header set, the
    origin absent - is not a browser, and must not be waved through into the
    router on the strength of resembling something that is.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/v1/projects/initialize",
            headers={"Access-Control-Request-Method": "POST"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_TOKEN_REQUIRED"


def _sidecar_env(**overrides: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(entry for entry in sys.path if entry)
    env["NEXUS_API_SESSION_TOKEN"] = SIDECAR_TOKEN
    env["NEXUS_API_PORT"] = "0"
    env.pop("NEXUS_API_CORS_ORIGINS", None)
    env.update(overrides)
    return env


def _read_handshake(process: subprocess.Popen[str], timeout: float = 30.0) -> dict[str, object]:
    """Read the single handshake line the sidecar emits on stdout."""
    result: queue.Queue[str] = queue.Queue(maxsize=1)

    def reader() -> None:
        assert process.stdout is not None
        result.put(process.stdout.readline())

    threading.Thread(target=reader, daemon=True).start()
    try:
        line = result.get(timeout=timeout)
    except queue.Empty:  # pragma: no cover - only reached on regression
        raise AssertionError("sidecar emitted no handshake line on stdout") from None
    assert line, "sidecar closed stdout without emitting a handshake line"
    return dict(json.loads(line))


def test_startup_announces_bound_port_as_json() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "nexus_api"],
        env=_sidecar_env(),
        # Explicit, so this case turns on the handshake alone: an inherited
        # stdin that happens to be a closed pipe would arm the liveness
        # watchdog and stop the sidecar for a reason unrelated to what is
        # under test here.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        handshake = _read_handshake(process)

        assert handshake["event"] == "nexus.api.listening"
        assert handshake["schemaVersion"] == "1.0.0"
        assert handshake["host"] == "127.0.0.1"
        assert handshake["pid"] == process.pid
        port = handshake["port"]
        assert isinstance(port, int)
        assert port > 0
        assert port != 8000

        # The announced port must be the port actually bound.
        response = httpx.get(
            f"http://127.0.0.1:{port}/healthz",
            headers={"Authorization": f"Bearer {SIDECAR_TOKEN}"},
            timeout=10.0,
        )
        assert response.status_code == 200
    finally:
        process.terminate()
        process.wait(timeout=10)


def _spawn_sidecar(**env: str) -> tuple[subprocess.Popen[str], int]:
    """Start a real sidecar and return it alongside the port it announced."""
    process = subprocess.Popen(
        [sys.executable, "-m", "nexus_api"],
        env=_sidecar_env(**env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        return process, int(str(_read_handshake(process)["port"]))
    except BaseException:
        process.kill()
        raise


def test_packaged_renderer_origin_is_allowed_when_the_token_is_a_secret() -> None:
    """A packaged Electron renderer loads over ``file://`` and sends ``Origin: null``.

    No origin allowlist contains that, so the shipped shell only works because
    the default is unrestricted - which is safe exactly while the token is the
    per-launch secret the supervisor injects, as it is here.
    """
    process, port = _spawn_sidecar()
    try:
        preflight = httpx.options(
            f"http://127.0.0.1:{port}/v1/projects/initialize",
            headers={
                "Origin": "null",
                "Access-Control-Request-Method": "POST",
                # A browser never attaches credentials to a preflight.
                "Access-Control-Request-Headers": "authorization,content-type",
            },
            timeout=10.0,
        )
        response = httpx.get(
            f"http://127.0.0.1:{port}/v1/projects/proj_abcdefghijklmnop",
            headers={"Origin": "null", "Authorization": f"Bearer {SIDECAR_TOKEN}"},
            timeout=10.0,
        )
    finally:
        process.terminate()
        process.wait(timeout=10)

    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") in {"*", "null"}

    # The token, not the origin allowlist, decides: the request reaches the app.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    assert response.headers.get("access-control-allow-origin") in {"*", "null"}


def test_dev_server_still_reaches_the_api_under_the_published_token() -> None:
    """Narrowing the default must not break `make dev`.

    The web development target runs at :5173 and presents the published token,
    which is the one arrangement the narrowed allowlist has to keep working -
    under both spellings of loopback, since the browser treats them as
    different origins.
    """
    process, port = _spawn_sidecar(NEXUS_API_SESSION_TOKEN="")
    try:
        responses = [
            httpx.get(
                f"http://127.0.0.1:{port}/v1/projects/proj_abcdefghijklmnop",
                headers={
                    "Origin": origin,
                    "Authorization": f"Bearer {DEV_SESSION_TOKEN}",
                },
                timeout=10.0,
            )
            for origin in ("http://localhost:5173", "http://127.0.0.1:5173")
        ]
    finally:
        process.terminate()
        process.wait(timeout=10)

    for response in responses:
        assert response.status_code == 404
        assert response.headers.get("access-control-allow-origin") is not None


def test_published_dev_token_is_not_combined_with_open_cors() -> None:
    """With no token configured the credential is public, so the origin matters.

    ``DEV_SESSION_TOKEN`` is a constant published in this repository and baked
    into the built web bundle, so any page the user happens to visit can present
    it. If the sidecar also answered every origin, that page could read the
    user's projects out of the API. The origin has to carry the boundary the
    token cannot.
    """
    process, port = _spawn_sidecar(NEXUS_API_SESSION_TOKEN="")
    try:
        response = httpx.get(
            f"http://127.0.0.1:{port}/v1/projects/proj_abcdefghijklmnop",
            headers={
                "Origin": "https://evil.example",
                "Authorization": f"Bearer {DEV_SESSION_TOKEN}",
            },
            timeout=10.0,
        )
    finally:
        process.terminate()
        process.wait(timeout=10)

    # The guessed credential still gets past the token check - that is the point:
    # it is published. What stops the page is that it may not read the answer.
    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") is None


def test_sidecar_exits_when_its_stdin_pipe_closes() -> None:
    """The stdin pipe is the only parent-death signal that works on Windows.

    ``_watch_parent`` notices a dead parent only because POSIX reparents
    orphans; Windows does not, so the pid never changes there and that watchdog
    never fires. The supervisor hands over a stdin pipe precisely so an EOF can
    say "the shell is gone" on every platform - which is worth nothing unless
    something actually reads it.
    """
    process, _ = _spawn_sidecar()
    try:
        assert process.stdin is not None
        assert process.poll() is None

        process.stdin.close()

        # Long enough to cover the sidecar's own shutdown grace period.
        process.wait(timeout=20)
    finally:
        if process.poll() is None:  # pragma: no cover - only reached on regression
            process.kill()
            process.wait(timeout=10)
            raise AssertionError("sidecar outlived the stdin pipe that signalled its parent")


# Stands in for the desktop shell: spawns the sidecar and then is killed.
PARENT_SOURCE = """
import subprocess
import sys

child = subprocess.Popen([sys.executable, "-m", "nexus_api"])
child.wait()
"""


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return False

    # On Linux, an unreaped child remains in the process table as a zombie ('Z')
    # until its reparented init/subreaper reaps it. os.kill(pid, 0) returns True
    # for zombies, falsely reporting an already-terminated process as alive.
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
                state = f.read().split(")")[-1].split()[0]
            if state == "Z":
                return False
        except (FileNotFoundError, ProcessLookupError, IndexError, OSError):
            return False
    return True


def test_sidecar_exits_when_parent_dies() -> None:
    parent = subprocess.Popen(
        [sys.executable, "-c", PARENT_SOURCE],
        env=_sidecar_env(),
        # No stdin pipe anywhere in this chain, so the sidecar can only notice
        # the death through `os.getppid()` - which is the watchdog under test.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    sidecar_pid = 0
    try:
        handshake = _read_handshake(parent)
        sidecar_pid = int(str(handshake["pid"]))
        assert sidecar_pid != parent.pid
        assert _pid_is_alive(sidecar_pid)

        parent.kill()
        parent.wait(timeout=10)

        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and _pid_is_alive(sidecar_pid):
            time.sleep(0.1)

        assert not _pid_is_alive(sidecar_pid), "sidecar outlived the parent that spawned it"
    finally:
        if sidecar_pid and _pid_is_alive(sidecar_pid):
            os.kill(sidecar_pid, 9)
        if parent.poll() is None:
            parent.kill()


def test_watchdog_keeps_the_parent_pid_read_before_the_handshake(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The shell may die the instant it reads the handshake.

    If the sidecar only read ``os.getppid()`` after announcing, a shell killed in
    that window would already have been replaced by the reparent target, the
    watchdog would wait on that pid forever, and the sidecar would be orphaned.
    This drives ``main()`` with the death landing exactly at the handshake, so it
    does not depend on scheduler timing the way the end-to-end test does.
    """
    from nexus_api import __main__ as sidecar

    shell_pid, reparent_pid = 4242, 1
    current_ppid = [shell_pid]
    events: list[str] = []
    watched: list[int] = []

    class _Socket:
        def getsockname(self) -> tuple[str, int]:
            return ("127.0.0.1", 50123)

    class _Thread:
        def __init__(  # type: ignore[no-untyped-def]
            self, *_args, target=None, args=(), name=None, daemon=None, **_kwargs
        ) -> None:
            self._name = name
            if target is sidecar._watch_parent:
                watched.append(args[1])

        def start(self) -> None:
            events.append(f"start:{self._name}")

    def _announce(host: str, port: int) -> None:
        events.append("announce")
        current_ppid[0] = reparent_pid  # the shell is killed as soon as it reads this

    monkeypatch.setattr(sidecar.os, "getppid", lambda: current_ppid[0])
    monkeypatch.setattr(sidecar, "_bind_listening_socket", lambda host, port: _Socket())
    monkeypatch.setattr(sidecar, "_announce", _announce)
    monkeypatch.setattr(sidecar.threading, "Thread", _Thread)
    monkeypatch.setattr(
        sidecar.uvicorn.Server, "run", lambda self, sockets=None: events.append("run")
    )

    sidecar.main()

    assert watched == [shell_pid]
    assert events == ["start:parent-watchdog", "start:stdin-watchdog", "announce", "run"]
