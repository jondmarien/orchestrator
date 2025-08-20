from __future__ import annotations

import asyncio
import logging
from typing import Any

from orchestrator.config import UpstreamServer
from orchestrator.mcp.aggregator.catalog import Catalog
from orchestrator.mcp.aggregator.client import UpstreamClient
from orchestrator.mcp.aggregator.merge import merge_capabilities
from orchestrator.mcp.aggregator.upstream import UpstreamProcess

logger = logging.getLogger(__name__)


class AggregationController:
    def __init__(
        self,
        upstream_processes: list[UpstreamProcess] | None = None,
        upstream_servers: list[UpstreamServer] | None = None,
        client_factory: type[UpstreamClient] | None = None,
    ) -> None:
        # from orchestrator.config import UpstreamServer  # local import to avoid cycles

        self._up_procs = upstream_processes or []
        self._up_cfgs = upstream_servers or []
        factory = client_factory or UpstreamClient
        if self._up_cfgs:
            # SDK-backed path: create placeholder processes carrying cfg for the client
            # We reuse UpstreamProcess dataclass shape by creating lightweight stand-ins
            from types import SimpleNamespace

            faux_processes: list[UpstreamProcess] = []
            for cfg in self._up_cfgs:
                faux = SimpleNamespace(cfg=cfg, process=None)  # type: ignore[var-annotated]
                faux_processes.append(faux)  # type: ignore[arg-type]
            self._clients = [factory(up) for up in faux_processes]  # type: ignore[list-item]
        else:
            self._clients = [factory(up) for up in self._up_procs]
        self._started = False
        self._rr = 0  # round-robin index
        self._catalog: Catalog | None = None

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
                # Rebuild the catalog to keep it fresh
                await self._build_catalog()
                return await self._aggregate_list(method)
            # Route tool calls to the specific upstream using the catalog
            if method == "tools/call" and isinstance(params, dict):
                tool_name = params.get("name")
                if isinstance(tool_name, str):
                    if self._catalog is None:
                        await self._build_catalog()
                    if self._catalog is not None:
                        target = self._catalog.get_tool_upstream(tool_name)
                        original = self._catalog.get_tool_original(tool_name)
                        if target is not None and original is not None:
                            for c in self._clients:
                                up = getattr(c, "upstream", None)
                                upstream_name = getattr(getattr(up, "cfg", None), "name", None)
                                if upstream_name == target:
                                    client = c
                                    # rewrite params name back to original
                                    params = dict(params)
                                    params["name"] = original
                                    break
            resp = await client.send_request(method, params, timeout=5.0, retries=0)
        except Exception as e:
            return {"error": {"code": -32001, "message": f"Upstream request failed: {e}"}}
        if "error" in resp:
            return {"error": resp["error"]}
        return {"result": resp.get("result")}

    @staticmethod
    def _sanitize(name: str) -> str:
        return name.replace("-", "_")

    async def _build_catalog(self) -> Catalog:
        await self._ensure_started()
        cat = Catalog()
        # tools
        tool_lists = await asyncio.gather(
            *(c.send_request("tools/list", None, timeout=5.0) for c in self._clients),
            return_exceptions=True,
        )
        for client, r in zip(self._clients, tool_lists, strict=False):
            if isinstance(r, Exception):
                continue
            lst = r.get("result") or []
            if isinstance(lst, list):
                for item in lst:
                    original_name = item.get("name")
                    if not isinstance(original_name, str):
                        continue
                    up = getattr(client, "upstream", None)
                    upstream_cfg = getattr(up, "cfg", None)
                    upstream_name = getattr(upstream_cfg, "name", None)
                    if not isinstance(upstream_name, str):
                        continue
                    # Per-server include/exclude filtering
                    include = getattr(upstream_cfg, "include_tools", None)
                    exclude = getattr(upstream_cfg, "exclude_tools", None)
                    norm = self._sanitize(original_name)
                    if include is not None:
                        include_norm = {self._sanitize(x) for x in include}
                        if norm not in include_norm:
                            continue
                    if exclude is not None:
                        exclude_norm = {self._sanitize(x) for x in exclude}
                        if norm in exclude_norm:
                            continue
                    # Build presented name and item copy
                    presented = f"{self._sanitize(upstream_name)}_{self._sanitize(original_name)}"
                    presented_item = dict(item)
                    presented_item["name"] = presented
                    desc = presented_item.get("description")
                    if isinstance(desc, str) and desc:
                        presented_item["description"] = f"[{upstream_name}] {desc}"
                    cat.set_tool(presented, presented_item, upstream_name, original_name)
        # prompts
        prompt_lists = await asyncio.gather(
            *(c.send_request("prompts/list", None, timeout=5.0) for c in self._clients),
            return_exceptions=True,
        )
        for client, r in zip(self._clients, prompt_lists, strict=False):
            if isinstance(r, Exception):
                continue
            lst = r.get("result") or []
            if isinstance(lst, list):
                for item in lst:
                    name = item.get("name")
                    if isinstance(name, str):
                        up = getattr(client, "upstream", None)
                        upstream_name = getattr(getattr(up, "cfg", None), "name", None)
                        if isinstance(upstream_name, str):
                            cat.set_prompt(name, item, upstream_name)
        # resources
        resource_lists = await asyncio.gather(
            *(c.send_request("resources/list", None, timeout=5.0) for c in self._clients),
            return_exceptions=True,
        )
        for client, r in zip(self._clients, resource_lists, strict=False):
            if isinstance(r, Exception):
                continue
            lst = r.get("result") or []
            if isinstance(lst, list):
                for item in lst:
                    name = item.get("name")
                    if isinstance(name, str):
                        up = getattr(client, "upstream", None)
                        upstream_name = getattr(getattr(up, "cfg", None), "name", None)
                        if isinstance(upstream_name, str):
                            cat.set_resource(name, item, upstream_name)
        self._catalog = cat
        return cat

    async def _aggregate_list(self, method: str) -> dict[str, Any]:
        await self._ensure_started()
        if method == "tools/list":
            # Legacy mode (process-based): preserve original names, merge by name
            if getattr(self, "_up_procs", None):
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
                from orchestrator.mcp.aggregator.merge import merge_named_lists

                merged = merge_named_lists(ok)
                return {"result": merged}
            # SDK/config mode: return presented names (prefixed + sanitized)
            if self._catalog is None:
                await self._build_catalog()
            assert self._catalog is not None
            items = [entry["item"] for entry in self._catalog.tools.values()]
            return {"result": items}
        # For prompts/resources, aggregate and merge by name
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
