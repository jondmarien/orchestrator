from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from orchestrator.rpc.jsonrpc import make_response
from orchestrator.transport.stdio import StdioJsonRpcFramer
from orchestrator.utils.stdout_guard import StdoutGuard

logger = logging.getLogger(__name__)


class MCPAggregatorServer:
    """
    Minimal skeleton for an MCP aggregator server.

    Responsibilities (to be implemented incrementally):
    - Initialize transports (stdio first; HTTP/SSE and WS later)
    - Maintain connections to multiple upstream MCP servers
    - Expose aggregated capabilities to the client (tools, prompts, resources)
    - Route JSON-RPC requests/responses between client and upstream servers
    - Enforce strict stdout hygiene for stdio transport
    """

    def __init__(
        self,
        name: str = "orchestrator-mcp-aggregator",
        initial_capabilities: dict[str, Any] | None = None,
        controller: Any | None = None,
    ) -> None:
        self.name = name
        self._shutdown_event = asyncio.Event()
        self._initial_capabilities = initial_capabilities or {
            "tools": {},
            "prompts": {},
            "resources": {},
        }
        # Optional aggregation controller for routing and capability merge
        if controller is not None:
            self._controller = controller

    def _write_stdout(self, framer: StdioJsonRpcFramer, obj: dict[str, Any]) -> None:
        data = framer.encode(obj)
        # Write framed bytes to stdout and flush. Keep stdout sacred for protocol only.
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    async def start_stdio(self) -> None:
        """Start a stdio JSON-RPC loop handling minimal MCP handshake."""
        logger.info("Starting MCP aggregator (stdio mode): %s", self.name)
        with StdoutGuard():
            framer = StdioJsonRpcFramer()

            async for msg in framer.iter_messages():
                method = msg.get("method")
                msg_id = msg.get("id")

                if method == "initialize":
                    # Aggregate capabilities from upstreams if a controller is present.
                    caps = self._initial_capabilities
                    controller = getattr(self, "_controller", None)
                    if controller is not None:
                        try:
                            caps = await controller.initialize_capabilities()
                        except Exception as e:  # keep serving even if aggregation fails
                            logger.error("Capability aggregation failed: %s", e)
                    # Apply client profile shaping (cursor: tools only)
                    import os

                    profile = os.environ.get("ORCH_CLIENT_PROFILE")
                    if profile == "cursor":
                        caps = {"tools": caps.get("tools", {}), "prompts": {}, "resources": {}}
                    result = {
                        "capabilities": caps,
                        "serverInfo": {"name": self.name, "version": "0.1.0"},
                    }
                    if msg_id is not None:
                        self._write_stdout(framer, make_response(msg_id, result))
                else:
                    # Route via controller if present; otherwise method not found
                    routed = None
                    controller = getattr(self, "_controller", None)
                    if controller is not None and msg_id is not None:
                        try:
                            routed = await controller.route_request(method, msg.get("params"))
                        except Exception as e:
                            logger.error("Routing error: %s", e)
                            routed = {"error": {"code": -32002, "message": str(e)}}
                    if msg_id is not None:
                        if routed and "result" in routed:
                            self._write_stdout(framer, make_response(msg_id, routed["result"]))
                        else:
                            err = (routed or {}).get("error") or {
                                "code": -32601,
                                "message": f"Method not found: {method}",
                            }
                            self._write_stdout(
                                framer, {"jsonrpc": "2.0", "id": msg_id, "error": err}
                            )

                if self._shutdown_event.is_set():
                    break

            # Wait for shutdown request if loop ended due to EOF
            await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        self._shutdown_event.set()

    async def __aenter__(self) -> MCPAggregatorServer:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.request_shutdown()
