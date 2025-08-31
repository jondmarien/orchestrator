from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from typing import Any


class Transport(abc.ABC):
    """Abstract transport for client communication."""

    @abc.abstractmethod
    async def serve(self) -> None:
        """Serve the transport until shutdown."""

    @abc.abstractmethod
    async def aclose(self) -> None:
        """Close transport resources."""


class MessageFramer(abc.ABC):
    """Abstract stream framer for JSON-RPC messages."""

    @abc.abstractmethod
    def encode(self, obj: Any) -> bytes: ...

    @abc.abstractmethod
    async def iter_messages(self) -> AsyncIterator[dict[str, Any]]: ...
