from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

from orchestrator.config import UpstreamServer
from orchestrator.mcp.aggregator.client import UpstreamClient
from orchestrator.mcp.aggregator.controller import AggregationController
from orchestrator.mcp.aggregator.upstream import UpstreamProcess


@pytest.mark.asyncio
async def test_tools_call_routes_via_catalog(monkeypatch):
    calls = []

    class MockClient:
        def __init__(self, up):
            self.up = up

        async def start(self):
            return None

        async def initialize(self):
            return {"capabilities": {}}

        async def send_request(self, method, params, **kwargs):
            if method == "tools/list":
                if self.up.cfg.name == "u1":
                    return {"result": [{"name": "a"}]}
                return {"result": [{"name": "b"}]}
            if method == "tools/call":
                calls.append(self.up.cfg.name)
                return {"result": {"ok": True}}
            return {"result": None}

    monkeypatch.setattr("orchestrator.mcp.aggregator.controller.UpstreamClient", MockClient)

    up1 = UpstreamProcess(cfg=cast(UpstreamServer, SimpleNamespace(name="u1")), process=AsyncMock())
    up2 = UpstreamProcess(cfg=cast(UpstreamServer, SimpleNamespace(name="u2")), process=AsyncMock())

    ctl = AggregationController([up1, up2], client_factory=cast(type[UpstreamClient], MockClient))

    # Build catalog via tools/list aggregation
    await ctl.route_request("tools/list", None)

    # Now tool call for 'b' should route to u2
    out = await ctl.route_request("tools/call", {"name": "b", "arguments": {}})
    assert out.get("result", {}).get("ok") is True
    assert calls[-1] == "u2"
