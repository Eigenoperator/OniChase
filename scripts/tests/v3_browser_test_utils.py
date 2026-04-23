#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


class QuietRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class LocalRepoServer:
    def __init__(self) -> None:
        handler = partial(QuietRequestHandler, directory=str(ROOT))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __enter__(self) -> "LocalRepoServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def run_v3_probe(probe: str, *, timeout: int = 180) -> dict[str, Any]:
    with LocalRepoServer() as server:
        page_url = f"{server.base_url}/docs/v3.html"
        command = [
            "node",
            str(ROOT / "scripts" / "tests" / "v3_browser_probe.js"),
            "--page-url",
            page_url,
            "--probe",
            probe,
        ]
        process = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    if process.returncode:
        raise AssertionError(
            f"v3 browser probe failed ({probe})\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{process.stdout}\n"
            f"stderr:\n{process.stderr}"
        )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"v3 browser probe did not return JSON ({probe})\n"
            f"stdout:\n{process.stdout}\n"
            f"stderr:\n{process.stderr}"
        ) from error
