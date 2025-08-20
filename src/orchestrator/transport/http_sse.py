# Placeholder foundation for HTTP+SSE transport implementation.
# This scaffolds an ASGI app surface and basic types without protocol wiring.
from __future__ import annotations

from typing import Any

import anyio


class HttpSseTransport:
    """Skeleton for an HTTP+SSE transport.

    Responsibilities (future work):
    - Expose an ASGI app with two endpoints:
      - POST /rpc for JSON-RPC requests over HTTP
      - GET /events for Server-Sent Events stream carrying notifications
    - Manage client sessions and backpressure using anyio streams
    - Bridge to the aggregator controller for method handling
    """

    def __init__(self) -> None:
        self._running = False

    async def run(self, host: str = "127.0.0.1", port: int = 7332) -> None:
        """Start the ASGI server (to be implemented in phase 2)."""
        self._running = True
        # No-op for now.
        await anyio.sleep(0)

    @property
    def is_running(self) -> bool:
        return self._running


# Minimal ASGI app scaffold
async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    assert scope["type"] == "http"
    path = scope.get("path", "/")

    if scope.get("method") == "GET" and path == "/events":
        # SSE endpoint placeholder
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        # Send a minimal comment to establish the stream, then close
        await send({"type": "http.response.body", "body": b": ok\n\n", "more_body": False})
        return

    if scope.get("method") == "POST" and path == "/rpc":
        # RPC endpoint placeholder
        await send(
            {
                "type": "http.response.start",
                "status": 501,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'{"error":{"code":-32601,"message":"Not implemented"}}',
                "more_body": False,
            }
        )
        return

    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"Not Found", "more_body": False})
