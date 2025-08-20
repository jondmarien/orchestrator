from __future__ import annotations

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
            # Minimal SSE setup with one keepalive comment
            headers = [(b"content-type", b"text/event-stream"), (b"cache-control", b"no-cache")]
            await send({"type": "http.response.start", "status": 200, "headers": headers})
            await send(
                {"type": "http.response.body", "body": b": keepalive\n\n", "more_body": False}
            )
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
                rpc_method = req.get("method")
                params = req.get("params")
                result = await controller.route_request(rpc_method, params)
                status = 200
                resp = result if isinstance(result, dict) else {"result": result}
            except Exception as e:
                status = 200
                resp = {"error": {"code": -32000, "message": f"Bad request: {e}"}}

            raw = json.dumps(resp, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
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
