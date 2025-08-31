from typing import cast
from unittest.mock import AsyncMock

import pytest

from orchestrator.config import UpstreamServer
from orchestrator.mcp.aggregator.client import UpstreamClient
from orchestrator.mcp.aggregator.controller import AggregationController
from orchestrator.mcp.aggregator.upstream import UpstreamProcess


class DummyProc(AsyncMock):
    def __init__(self, responses: dict[str, dict]):
        super().__init__()
        self._responses = responses
        self.stdin = AsyncMock()
        self.stdout = AsyncMock()

    async def send(self, method: str):
        return self._responses.get(method, {"result": []})


@pytest.mark.asyncio
async def test_aggregate_list_tools_merges_unique_names(monkeypatch):
    # Prepare two upstream clients with overlapping tool names
    resp1 = {"result": [{"name": "a"}, {"name": "b"}]}
    resp2 = {"result": [{"name": "b"}, {"name": "c"}]}

    # Mock UpstreamClient to return these results
    from orchestrator.mcp.aggregator import client as client_mod

    class MockClient:
        def __init__(self, up):
            self.up = up

        async def start(self):
            return None

        async def initialize(self):
            return {"capabilities": {}}

        async def send_request(self, method, params, **kwargs):
            if method == "tools/list":
                return resp1 if self.up.cfg.name == "u1" else resp2
            return {"result": None}

    monkeypatch.setattr(client_mod, "UpstreamClient", MockClient)

    # Build controller with two upstream processes
    from types import SimpleNamespace

    up1 = UpstreamProcess(cfg=cast(UpstreamServer, SimpleNamespace(name="u1")), process=AsyncMock())
    up2 = UpstreamProcess(cfg=cast(UpstreamServer, SimpleNamespace(name="u2")), process=AsyncMock())
    ctl = AggregationController([up1, up2], client_factory=cast(type[UpstreamClient], MockClient))

    out = await ctl.route_request("tools/list", None)
    assert "result" in out
    names = sorted([t["name"] for t in out["result"]])
    assert names == ["a", "b", "c"]
