from __future__ import annotations

import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.helpers import FIXTURES

pytest_plugins: list[str] = []


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def translate_path(self, path: str) -> str:
        translated = super().translate_path(path)
        if os.path.exists(translated):
            return translated
        if not os.path.splitext(translated)[1]:
            html = translated + ".html"
            if os.path.exists(html):
                return html
        return translated


@pytest.fixture
def serve_site():
    servers: list[ThreadingHTTPServer] = []

    def _start(site_dir: str) -> str:
        directory = FIXTURES / site_dir
        handler = partial(_QuietHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        host, port = server.server_address
        return f"http://{host}:{port}/"

    yield _start
    for server in servers:
        server.shutdown()


class _UAGatedHandler(_QuietHandler):
    """Serves normally, but refuses any user-agent matching a blocked token.

    Mirrors an edge/WAF rule that denies named AI crawlers while robots.txt says
    nothing about them.
    """

    blocked_tokens: tuple[str, ...] = ()

    def _is_blocked(self) -> bool:
        ua = self.headers.get("User-Agent", "")
        return any(token.lower() in ua.lower() for token in self.blocked_tokens)

    def do_GET(self) -> None:  # noqa: N802
        if self._is_blocked():
            self.send_error(403, "Forbidden")
            return
        super().do_GET()

    def do_HEAD(self) -> None:  # noqa: N802
        if self._is_blocked():
            self.send_error(403, "Forbidden")
            return
        super().do_HEAD()


@pytest.fixture
def serve_ua_gated_site():
    """Start a fixture site that 403s the given user-agent tokens."""
    servers: list[ThreadingHTTPServer] = []

    def _start(site_dir: str, blocked_tokens: tuple[str, ...]) -> str:
        directory = FIXTURES / site_dir

        class _Handler(_UAGatedHandler):
            pass

        _Handler.blocked_tokens = blocked_tokens
        handler = partial(_Handler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        host, port = server.server_address
        return f"http://{host}:{port}/"

    yield _start
    for server in servers:
        server.shutdown()
