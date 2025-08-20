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


def filter_tools_by_names(
    all_tools: list[dict[str, Any]], include: list[str] | None, exclude: list[str] | None
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tool in all_tools:
        name = tool.get("name")
        if not isinstance(name, str):
            continue
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        result.append(tool)
    return result


def merge_named_lists(lists: Iterable[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for lst in lists:
        for item in lst:
            name = item.get("name")
            if isinstance(name, str) and name not in seen:
                seen.add(name)
                merged.append(item)
    return merged
