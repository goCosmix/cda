#!/usr/bin/env python3
"""
Code Data Ark Intelligence Portal
Entry point: exposes application() and start_server() for the CLI.
"""

import socket
from wsgiref.simple_server import make_server, WSGIServer

from cda.ui.routes import application  # noqa: F401


def start_server(host="127.0.0.1", port=10001):
    """Start WSGI server."""
    print(f"Starting Code Data Ark Intelligence Portal at http://{host}:{port}")
    print("Press Ctrl+C to stop.")

    class ReusableTCPServer(WSGIServer):
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()

    httpd = make_server(host, port, application, server_class=ReusableTCPServer)
    httpd.serve_forever()


if __name__ == "__main__":
    start_server()
