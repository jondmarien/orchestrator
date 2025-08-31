from __future__ import annotations

import asyncio
from typing import Any


class HttpSseTransport:
    """HTTP+SSE transport wired to the aggregation controller.

    Endpoints:
    - POST /rpc: JSON-RPC 2.0 requests to controller.route_request
    - GET  /events: SSE stream placeholder (keepalive comments)
    """

    def __init__(self) -> None:
        self._running = False

    async def run(self, controller: Any, host: str = "127.0.0.1", port: int = 7332) -> None:
        """Start the ASGI server via uvicorn if available; otherwise, no-op."""
        try:
            import uvicorn  # type: ignore
        except Exception:
            self._running = False
            return
        self._running = True
        config = uvicorn.Config(create_app(controller), host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


def create_app(controller: Any):
    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        assert scope["type"] == "http"
        path = scope.get("path", "/")
        method = scope.get("method")

        if method == "GET" and path == "/events":
            # Persistent SSE with periodic keepalive
            headers = [
                (b"content-type", b"text/event-stream"),
                (b"cache-control", b"no-cache"),
                (b"connection", b"keep-alive"),
            ]
            await send({"type": "http.response.start", "status": 200, "headers": headers})
            try:
                # Initial comment
                await send(
                    {"type": "http.response.body", "body": b": connected\n\n", "more_body": True}
                )
                while True:
                    await asyncio.sleep(15)
                    await send(
                        {
                            "type": "http.response.body",
                            "body": b": keepalive\n\n",
                            "more_body": True,
                        }
                    )
            except Exception:
                # Client likely disconnected
                pass
            return

        if method == "GET" and path == "/health":
            # Basic health endpoint
            try:
                stats = await controller.get_stats()
                import json

                raw = json.dumps({"status": "ok", **stats}, ensure_ascii=False).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": raw, "more_body": False})
            except Exception:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send({"type": "http.response.body", "body": b"error", "more_body": False})
            return

        if method == "POST" and path == "/rpc":
            body = b""
            more = True
            while more:
                message = await receive()
                if message["type"] != "http.request":
                    break
                body += message.get("body", b"") or b""
                more = message.get("more_body", False)

            try:
                import json

                req = json.loads(body.decode("utf-8")) if body else {}
                rpc_id = req.get("id")
                rpc_method = req.get("method")
                params = req.get("params")
                result = await controller.route_request(rpc_method, params)
                status = 200
                # Wrap with JSON-RPC envelope and echo id
                if isinstance(result, dict) and ("result" in result or "error" in result):
                    # result already normalized from controller
                    payload = {"jsonrpc": "2.0", "id": rpc_id, **result}
                else:
                    payload = {"jsonrpc": "2.0", "id": rpc_id, "result": result}
            except Exception as e:
                status = 200
                payload = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32000, "message": f"Bad request: {e}"},
                }

            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": raw, "more_body": False})
            return

        await send(
            {
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"Not Found", "more_body": False})

    return app
