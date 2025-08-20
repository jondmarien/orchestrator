from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Catalog:
    tools: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )  # presented_name -> {item, upstream, original_name}
    prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_tool(
        self, presented_name: str, item: dict[str, Any], upstream: str, original_name: str
    ) -> None:
        self.tools[presented_name] = {
            "item": item,
            "upstream": upstream,
            "original_name": original_name,
        }

    def set_prompt(self, name: str, item: dict[str, Any], upstream: str) -> None:
        self.prompts[name] = {"item": item, "upstream": upstream}

    def set_resource(self, name: str, item: dict[str, Any], upstream: str) -> None:
        self.resources[name] = {"item": item, "upstream": upstream}

    def get_tool_upstream(self, presented_name: str) -> str | None:
        entry = self.tools.get(presented_name)
        return entry.get("upstream") if entry else None

    def get_tool_original(self, presented_name: str) -> str | None:
        entry = self.tools.get(presented_name)
        return entry.get("original_name") if entry else None
