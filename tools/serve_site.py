#!/usr/bin/env python3
"""Serve a built portfolio preview without dropping parallel image requests."""

from __future__ import annotations

import argparse
from functools import partial
import http.server
from pathlib import Path


class PreviewHTTPServer(http.server.ThreadingHTTPServer):
    """Small local server sized for browsers loading many images at once."""

    request_queue_size = 128
    daemon_threads = True
    allow_reuse_address = True


class QuietRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # request noise, not results
        pass


def create_preview_server(
    root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    quiet: bool = False,
) -> PreviewHTTPServer:
    """Create a loopback-only threaded server rooted at ``root``."""

    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Preview root is not a directory: {root}")
    handler_class = QuietRequestHandler if quiet else http.server.SimpleHTTPRequestHandler
    handler = partial(handler_class, directory=str(root))
    return PreviewHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True, help="Built site directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    with create_preview_server(args.site, host=args.host, port=args.port) as server:
        host, port = server.server_address[:2]
        print(f"Serving {args.site.resolve()} at http://{host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
