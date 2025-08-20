from __future__ import annotations

import asyncio
import logging
from typing import Any

from orchestrator.mcp.aggregator.client import UpstreamClient
from orchestrator.mcp.aggregator.merge import merge_capabilities
from orchestrator.mcp.aggregator.upstream import UpstreamProcess

logger = logging.getLogger(__name__)


class AggregationController:
    def __init__(self, upstream_processes: list[UpstreamProcess]) -> None:
        self._up_procs = upstream_processes
        self._clients: list[UpstreamClient] = [UpstreamClient(up) for up in upstream_processes]
        self._started = False

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

    async def aclose(self) -> None:
        await asyncio.gather(*(c.close() for c in self._clients), return_exceptions=True)
