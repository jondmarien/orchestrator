import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from orchestrator.mcp.aggregator.client import UpstreamClient


class DummyStreams:
    def __init__(self):
        self._r = asyncio.StreamReader()
        self._w_transport, self._w_protocol = None, None
        self._write_buf = bytearray()

    @property
    def reader(self):
        return self._r

    @property
    def writer(self):
        class W:
            def __init__(self, outer):
                self.outer = outer

            def write(self, data: bytes):
                self.outer._write_buf.extend(data)

            async def drain(self):
                return None

        return W(self)

    def feed_from(self, msg: bytes):
        self._r.feed_data(msg)

    def feed_eof(self):
        self._r.feed_eof()


def frame_json(obj: dict) -> bytes:
    import json

    body = json.dumps(obj, separators=(",", ":")).encode()
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()
    return header + body


@pytest.mark.asyncio
async def test_upstream_client_initialize():
    # Mock a process with stdin/stdout pipes
    proc = AsyncMock()
    streams = DummyStreams()
    proc.stdout = streams.reader
    proc.stdin = streams.writer

    from orchestrator.mcp.aggregator.upstream import UpstreamProcess

    up = UpstreamProcess(cfg=Mock(name="cfg"), process=proc)
    client = UpstreamClient(upstream=up)

    await client.start()

    async def respond():
        # Capture the written request and respond with a framed result
        await asyncio.sleep(0.01)
        # Respond with initialize result
        streams.feed_from(
            frame_json(
                {"jsonrpc": "2.0", "id": 1, "result": {"capabilities": {"tools": {"a": {}}}}}
            )
        )

    asyncio.create_task(respond())
    resp = await client.initialize()
    assert "id" in resp and resp["id"] == 1
    assert "result" in resp
