"""A real HTTP server on localhost for tests that need something to talk to."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest


class Handler(BaseHTTPRequestHandler):
    """Tiny API: /login, /me, /echo, /status/N, /slow, /text, /items."""

    protocol_version = "HTTP/1.1"
    log = []  # (method, path) of every request seen

    def log_message(self, *args) -> None:  # silence stderr
        pass

    def _reply(self, status: int, payload, ctype: str = "application/json", extra=None) -> None:
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _handle(self) -> None:
        url = urlparse(self.path)
        body = self._body()
        Handler.log.append((self.command, self.path))
        path = url.path
        if path == "/login" and self.command == "POST":
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                return self._reply(400, {"error": "bad json"})
            if data.get("user") == "raj":
                return self._reply(
                    200, {"token": "abc123", "user": {"id": 7, "name": "raj"}},
                    extra={"X-Request-Id": "req-1"},
                )
            return self._reply(401, {"error": "unknown user"})
        if path == "/me":
            if self.headers.get("Authorization") != "Bearer abc123":
                return self._reply(401, {"error": "unauthorised"})
            return self._reply(200, {"id": 7, "name": "raj", "roles": ["admin", "dev"]})
        if path == "/echo":
            return self._reply(
                200,
                {
                    "method": self.command,
                    "query": parse_qs(url.query),
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": body.decode("utf-8"),
                },
            )
        if path.startswith("/status/"):
            return self._reply(int(path.rsplit("/", 1)[1]), {"status": path.rsplit("/", 1)[1]})
        if path == "/slow":
            time.sleep(1.5)
            return self._reply(200, {"slow": True})
        if path == "/text":
            return self._reply(200, "héllo".encode(), ctype="text/plain")
        if path == "/items":
            return self._reply(200, [{"id": 1}, {"id": 2}, {"id": 3}])
        return self._reply(404, {"error": "not found", "path": path})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = _handle


@pytest.fixture(scope="session")
def server():
    """Base URL of a local server, e.g. ``http://127.0.0.1:54321``."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture(autouse=True)
def _clear_log():
    Handler.log.clear()
    yield
