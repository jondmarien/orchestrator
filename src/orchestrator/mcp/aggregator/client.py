from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from orchestrator.mcp.aggregator.upstream import UpstreamProcess

logger = logging.getLogger(__name__)


class UpstreamClient:
    """
    Minimal JSON-RPC client over stdio for an upstream MCP server.
    """

    def __init__(self, upstream: UpstreamProcess) -> None:
        self.upstream = upstream
        self._stdout = upstream.process.stdout  # type: ignore[assignment]
        self._stdin = upstream.process.stdin  # type: ignore[assignment]
        self._reader_task: asyncio.Task[None] | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._closed = False

    async def start(self) -> None:
        if self._reader_task is None:
            self._reader_task = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

    async def initialize(self) -> dict:
        return await self.send_request("initialize", {})

    async def send_request(self, method: str, params: Any | None = None) -> dict:
        req_id = self._next_id
        self._next_id += 1
        req = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            req["params"] = params
        data = json.dumps(req, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        fut: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        assert self._stdin is not None
        self._stdin.write(header + data)
        await self._stdin.drain()
        return await fut

    async def _read_loop(self) -> None:
        assert self._stdout is not None
        while not self._closed:
            # Read header lines until blank line
            header_line = await self._stdout.readline()
            if not header_line:
                break
            if not header_line.lower().startswith(b"content-length:"):
                # skip until blank
                while header_line not in (b"\r\n", b"\n", b""):
                    header_line = await self._stdout.readline()
                continue
            length = int(header_line.split(b":")[1].strip())
            # blank line
            _ = await self._stdout.readline()
            body = await self._stdout.readexactly(length)
            try:
                msg = json.loads(body)
            except Exception:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                req_id = msg.get("id")
                fut = self._pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(msg)
