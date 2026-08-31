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
