from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from orchestrator.mcp.aggregator.upstream import UpstreamProcess

logger = logging.getLogger(__name__)


# Attempt to import the official MCP Python SDK. If available, we'll use it to back the client.
try:  # pragma: no cover - import path may vary by environment
    from mcp.client.session import ClientSession  # type: ignore
    from mcp.client.stdio import stdio_client  # type: ignore

    _MCP_SDK_AVAILABLE = True
except Exception:  # pragma: no cover
    ClientSession = None  # type: ignore
    stdio_client = None  # type: ignore
    _MCP_SDK_AVAILABLE = False


class _FallbackUpstreamClient:
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

    async def send_request(
        self,
        method: str,
        params: Any | None = None,
        *,
        timeout: float | None = 5.0,
        retries: int = 0,
    ) -> dict:
        req_id = self._next_id
        self._next_id += 1
        req = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            req["params"] = params
        data = json.dumps(req, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        attempt = 0
        while True:
            fut: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
            self._pending[req_id] = fut
            assert self._stdin is not None
            self._stdin.write(header + data)
            await self._stdin.drain()
            try:
                if timeout is not None:
                    return await asyncio.wait_for(fut, timeout=timeout)
                return await fut
            except TimeoutError:
                attempt += 1
                logger.warning(
                    "Upstream request timed out: method=%s id=%s attempt=%d",
                    method,
                    req_id,
                    attempt,
                )
                # Clean up pending on timeout
                self._pending.pop(req_id, None)
                if attempt > retries:
                    raise
                await asyncio.sleep(min(0.1 * (2 ** (attempt - 1)), 1.0))
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


class UpstreamClient:
    """
    SDK-backed upstream client.

    If the official MCP Python SDK is available and an upstream configuration is
    provided, use stdio_client + ClientSession to manage the connection. Otherwise,
    fall back to the lightweight stdio JSON-RPC client.
    """

    def __init__(self, upstream: UpstreamProcess) -> None:
        self.upstream = upstream
        self._fallback: _FallbackUpstreamClient | None = None
        self._stdio_cm = None
        self._session_cm = None
        self._session: Any | None = None
        self._initialized_via_sdk = False

    async def start(self) -> None:
        if _MCP_SDK_AVAILABLE:
            # If upstream.process is None, we are in SDK mode using config only.
            cfg = getattr(self.upstream, "cfg", None)
            proc = getattr(self.upstream, "process", None)
            if cfg is not None and proc is None:
                # Map our config to StdioServerParameters
                try:
                    from mcp.client.stdio import StdioServerParameters  # type: ignore
                except Exception:
                    # Fallback if parameters import path changes
                    StdioServerParameters = None  # type: ignore

                if StdioServerParameters is None:
                    # SDK not providing expected API; use fallback
                    self._fallback = _FallbackUpstreamClient(self.upstream)
                    await self._fallback.start()
                    return

                cmd_parts = list(getattr(cfg, "command", []))
                if not cmd_parts:
                    raise ValueError("UpstreamServer.command is empty")
                command = cmd_parts[0]
                args = cmd_parts[1:]
                env = dict(getattr(cfg, "env", {}) or {})

                # Enter stdio_client and ClientSession contexts manually to keep them open
                self._stdio_cm = stdio_client(
                    StdioServerParameters(command=command, args=args, env=env)
                )
                read, write = await self._stdio_cm.__aenter__()  # type: ignore[attr-defined]
                self._session_cm = ClientSession(read, write)  # type: ignore[call-arg]
                self._session = await self._session_cm.__aenter__()
                return

        # Default fallback path (SDK unavailable or running process provided)
        self._fallback = _FallbackUpstreamClient(self.upstream)
        await self._fallback.start()

    async def close(self) -> None:
        if self._fallback is not None:
            await self._fallback.close()
            return
        # Close SDK contexts in LIFO order
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                pass
            finally:
                self._session_cm = None
                self._session = None
        if self._stdio_cm is not None:
            try:
                await self._stdio_cm.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                pass
            finally:
                self._stdio_cm = None

    async def initialize(self) -> dict:
        if self._fallback is not None:
            return await self._fallback.initialize()
        assert self._session is not None, "SDK session not started"
        # Call SDK initialize and adapt to our aggregator merge expectations
        init = await self._session.initialize()
        # Try to dump to dict; pydantic model_dump preferred
        try:
            dumped = init.model_dump()  # type: ignore[attr-defined]
        except Exception:
            dumped = dict(getattr(init, "__dict__", {}))
        self._initialized_via_sdk = True
        return {"result": dumped}

    async def send_request(
        self,
        method: str,
        params: Any | None = None,
        *,
        timeout: float | None = 5.0,
        retries: int = 0,
    ) -> dict:
        if self._fallback is not None:
            return await self._fallback.send_request(
                method, params, timeout=timeout, retries=retries
            )

        assert self._session is not None, "SDK session not started"
        m = method
        try:
            if m == "tools/list":
                resp = await self._session.list_tools()
                # resp.tools is a list of models
                tools = []
                for t in getattr(resp, "tools", []) or []:
                    try:
                        tools.append(t.model_dump())  # type: ignore[attr-defined]
                    except Exception:
                        tools.append(dict(getattr(t, "__dict__", {})))
                return {"result": tools}

            if m == "prompts/list":
                resp = await self._session.list_prompts()
                prompts = []
                for p in getattr(resp, "prompts", []) or []:
                    try:
                        prompts.append(p.model_dump())  # type: ignore[attr-defined]
                    except Exception:
                        prompts.append(dict(getattr(p, "__dict__", {})))
                return {"result": prompts}

            if m == "resources/list":
                resp = await self._session.list_resources()
                resources = []
                for r in getattr(resp, "resources", []) or []:
                    try:
                        resources.append(r.model_dump())  # type: ignore[attr-defined]
                    except Exception:
                        resources.append(dict(getattr(r, "__dict__", {})))
                return {"result": resources}

            if m == "tools/call":
                name = None
                arguments = None
                if isinstance(params, dict):
                    name = params.get("name")
                    arguments = params.get("arguments") or params.get("args") or {}
                if not isinstance(name, str):
                    return {
                        "error": {"code": -32602, "message": "Invalid params: missing tool name"}
                    }
                result = await self._session.call_tool(name, arguments=arguments or {})
                # Result has content (blocks) and possibly structuredContent
                try:
                    dumped = result.model_dump()  # type: ignore[attr-defined]
                except Exception:
                    dumped = dict(getattr(result, "__dict__", {}))
                return {"result": dumped}

            return {
                "error": {"code": -32601, "message": f"Method not implemented via SDK: {method}"}
            }
        except Exception as e:
            return {"error": {"code": -32001, "message": f"SDK request failed: {e}"}}
