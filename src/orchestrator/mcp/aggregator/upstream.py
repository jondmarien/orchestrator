from __future__ import annotations

import asyncio
import asyncio.subprocess as subprocess
import contextlib
import logging
import os
from dataclasses import dataclass

from orchestrator.config import UpstreamServer

logger = logging.getLogger(__name__)


@dataclass
class UpstreamProcess:
    cfg: UpstreamServer
    process: subprocess.Process

    @property
    def name(self) -> str:
        return self.cfg.name

    def is_running(self) -> bool:
        return self.process.returncode is None

    async def terminate(self, timeout: float = 5.0) -> None:
        if self.process.returncode is not None:
            return
        try:
            self.process.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(self.process.wait(), timeout=timeout)
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                self.process.kill()


class UpstreamProcessManager:
    """Manage lifecycle of multiple stdio-based upstream MCP servers."""

    def __init__(self) -> None:
        self._procs: dict[str, UpstreamProcess] = {}
        self._lock = asyncio.Lock()

    async def start_one(self, cfg: UpstreamServer) -> UpstreamProcess:
        env = os.environ.copy()
        env.update(cfg.env)
        logger.info("Starting upstream server: %s", cfg.name)
        proc = await asyncio.create_subprocess_exec(
            *cfg.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        up = UpstreamProcess(cfg=cfg, process=proc)
        async with self._lock:
            self._procs[cfg.name] = up
        return up

    async def start_all(self, servers: list[UpstreamServer]) -> list[UpstreamProcess]:
        results: list[UpstreamProcess] = []
        for cfg in servers:
            up = await self.start_one(cfg)
            results.append(up)
        return results

    async def stop_all(self, timeout: float = 5.0) -> None:
        async with self._lock:
            procs = list(self._procs.values())
            self._procs.clear()
        await asyncio.gather(*(p.terminate(timeout=timeout) for p in procs), return_exceptions=True)

    def get(self, name: str) -> UpstreamProcess | None:
        return self._procs.get(name)
