import asyncio

import pytest

from orchestrator.mcp.aggregator import MCPAggregatorServer


@pytest.mark.asyncio
async def test_server_start_and_shutdown():
    server = MCPAggregatorServer(name="test")

    async def run_and_shutdown():
        # Schedule a shutdown after a brief delay
        async def delayed_shutdown():
            await asyncio.sleep(0.05)
            server.request_shutdown()

        asyncio.create_task(delayed_shutdown())
        await server.start_stdio()

    await run_and_shutdown()
