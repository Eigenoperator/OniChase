#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def find_open_port(preferred_port: int, host: str) -> int:
    port = preferred_port
    while port < preferred_port + 50:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, port)) != 0:
                return port
        port += 1
    raise RuntimeError(f"Could not find an open port near {preferred_port}.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the OniChase local website and optionally open a page.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port. Default: 8000")
    parser.add_argument("--page", default="ui/planner.html", help="Page to open. Default: ui/planner.html")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open a browser.")
    args = parser.parse_args()

    port = find_open_port(args.port, args.host)
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer((args.host, port), handler)
    url = f"http://{args.host}:{port}/{args.page.lstrip('/')}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("OniChase local site is running.")
    print(f"Root: {ROOT}")
    print(f"URL:  {url}")
    print("Press Ctrl+C to stop.")

    if not args.no_browser:
      # Give the server a moment so the browser doesn't race the socket.
        time.sleep(0.35)
        webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping local site...")
    finally:
        server.shutdown()
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
