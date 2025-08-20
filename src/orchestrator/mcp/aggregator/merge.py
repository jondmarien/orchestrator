from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def merge_capabilities(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    tools: dict[str, Any] = {}
    prompts: dict[str, Any] = {}
    resources: dict[str, Any] = {}
    for res in results:
        caps = (
            res.get("result", {}).get("capabilities")
            if "result" in res
            else res.get("capabilities", {})
        )
        if not isinstance(caps, dict):
            continue
        for k, target in (("tools", tools), ("prompts", prompts), ("resources", resources)):
            v = caps.get(k, {})
            if isinstance(v, dict):
                target.update(v)
    return {"tools": tools, "prompts": prompts, "resources": resources}
