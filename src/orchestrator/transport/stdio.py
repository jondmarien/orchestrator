from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator
from typing import Any

from orchestrator.transport.base import MessageFramer


class StdioJsonRpcFramer(MessageFramer):
    """Framer using Content-Length based delimiting (JSON-RPC over stdio).

    Uses blocking reads from sys.stdin.buffer executed via asyncio.to_thread
    for cross-platform compatibility (not relying on connect_read_pipe).
    """

    def __init__(self) -> None:
        pass

    def encode(self, obj: Any) -> bytes:
        body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body

    @staticmethod
    def _read_message_blocking() -> dict[str, Any] | None:
        try:
            # Read headers until blank line
            header_line = sys.stdin.buffer.readline()
            if header_line == b"":
                return None  # EOF
            # We accept optional extra headers but only require Content-Length
            if not header_line.lower().startswith(b"content-length:"):
                # Skip unknown headers until blank line or find content-length
                length = None
                headers = [header_line]
                while True:
                    line = sys.stdin.buffer.readline()
                    if line in (b"\r\n", b"\n", b""):
                        break
                    headers.append(line)
                    if line.lower().startswith(b"content-length:"):
                        length = int(line.split(b":")[1].strip())
                if length is None:
                    return None
            else:
                length = int(header_line.split(b":")[1].strip())
                # Read and discard the blank line
                _ = sys.stdin.buffer.readline()
            body = sys.stdin.buffer.read(length)
            if not body:
                return None
            return json.loads(body)
        except OSError:
            # e.g., under pytest capture, reading stdin is disallowed
            return None

    async def iter_messages(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            msg = await asyncio.to_thread(self._read_message_blocking)
            if msg is None:
                break
            yield msg
