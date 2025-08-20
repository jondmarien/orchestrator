from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UpstreamServer(BaseModel):
    name: str
    command: list[str] = Field(..., description="Command to start the upstream MCP server (stdio)")
    env: dict[str, str] = Field(default_factory=dict)
    include_tools: list[str] | None = None
    exclude_tools: list[str] | None = None


class TransportConfig(BaseModel):
    mode: Literal["stdio", "http-sse", "ws"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 7332
    sse_path: str = "/events"


class AggregatorConfig(BaseModel):
    name: str = "orchestrator-mcp-aggregator"
    upstream: list[UpstreamServer] = Field(default_factory=list)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    strict_stdout: bool = True
    include_tools: list[str] | None = None
    exclude_tools: list[str] | None = None
    client_profile: Literal["cursor", "windsurf"] | None = None


__all__ = [
    "UpstreamServer",
    "TransportConfig",
    "AggregatorConfig",
]
