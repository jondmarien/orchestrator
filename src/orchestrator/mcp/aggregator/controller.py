from __future__ import annotations

import asyncio
import logging
from typing import Any

from orchestrator.mcp.aggregator.client import UpstreamClient
from orchestrator.mcp.aggregator.merge import merge_capabilities
from orchestrator.mcp.aggregator.upstream import UpstreamProcess

logger = logging.getLogger(__name__)


class AggregationController:
    def __init__(
        self,
        upstream_processes: list[UpstreamProcess],
        client_factory: type[UpstreamClient] | None = None,
    ) -> None:
        self._up_procs = upstream_processes
        factory = client_factory or UpstreamClient
        self._clients: list[UpstreamClient] = [factory(up) for up in upstream_processes]
        self._started = False
        self._rr = 0  # round-robin index

    async def _ensure_started(self) -> None:
        if not self._started:
            await asyncio.gather(*(c.start() for c in self._clients))
            self._started = True

    async def initialize_capabilities(self) -> dict[str, Any]:
        await self._ensure_started()
        # Run initialize on all upstreams concurrently
        results = await asyncio.gather(
            *(c.initialize() for c in self._clients), return_exceptions=True
        )
        ok_results: list[dict[str, Any]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Upstream initialize failed: %s", r)
                continue
            ok_results.append(r)
        return merge_capabilities(ok_results)

    async def route_request(self, method: str, params: Any | None) -> dict[str, Any]:
        """Route a request to an upstream and return a simplified response.

        For now, use round-robin across available clients and return the response body
        with either a "result" or "error" key.
        """
        await self._ensure_started()
        if not self._clients:
            return {"error": {"code": -32000, "message": "No upstreams available"}}
        # Apply global tool include/exclude filtering when routing tool execution
        import os

        if method == "tools/call":
            include = os.environ.get("ORCH_INCLUDE_TOOLS")
            exclude = os.environ.get("ORCH_EXCLUDE_TOOLS")
            if include or exclude:
                name = (params or {}).get("name") if isinstance(params, dict) else None
                if isinstance(name, str):
                    if include and name not in include.split(","):
                        return {"error": {"code": -32601, "message": f"Tool not allowed: {name}"}}
                    if exclude and name in exclude.split(","):
                        return {"error": {"code": -32601, "message": f"Tool excluded: {name}"}}
        client = self._clients[self._rr % len(self._clients)]
        self._rr += 1
        try:
            # Handle discovery methods specially (list* aggregation)
            if method in {"tools/list", "prompts/list", "resources/list"}:
                return await self._aggregate_list(method)
            resp = await client.send_request(method, params, timeout=5.0, retries=0)
        except Exception as e:
            return {"error": {"code": -32001, "message": f"Upstream request failed: {e}"}}
        if "error" in resp:
            return {"error": resp["error"]}
        return {"result": resp.get("result")}

    async def _aggregate_list(self, method: str) -> dict[str, Any]:
        await self._ensure_started()
        results = await asyncio.gather(
            *(c.send_request(method, None, timeout=5.0) for c in self._clients),
            return_exceptions=True,
        )
        ok: list[list[dict[str, Any]]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Upstream %s failed: %s", method, r)
                continue
            lst = r.get("result") or []
            if isinstance(lst, list):
                ok.append(lst)
        # Merge by unique name
        from orchestrator.mcp.aggregator.merge import merge_named_lists

        merged = merge_named_lists(ok)
        return {"result": merged}

    async def aclose(self) -> None:
        await asyncio.gather(*(c.close() for c in self._clients), return_exceptions=True)
