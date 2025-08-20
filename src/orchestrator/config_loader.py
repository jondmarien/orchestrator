from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from orchestrator.config import AggregatorConfig


def _apply_env_overrides(cfg: AggregatorConfig) -> AggregatorConfig:
    import os

    name = os.environ.get("ORCH_NAME")
    if name:
        cfg.name = name
    profile = os.environ.get("ORCH_CLIENT_PROFILE")
    if profile in {"cursor", "windsurf"}:
        cfg.client_profile = profile  # type: ignore[assignment]
    include = os.environ.get("ORCH_INCLUDE_TOOLS")
    if include:
        cfg.include_tools = [s for s in include.split(",") if s]
    exclude = os.environ.get("ORCH_EXCLUDE_TOOLS")
    if exclude:
        cfg.exclude_tools = [s for s in exclude.split(",") if s]
    return cfg


def load_config(path: str) -> AggregatorConfig:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required to load YAML configs. Install with `uv add pyyaml`."
            ) from e
        data = yaml.safe_load(text)  # type: ignore[no-redef]
    else:
        data = json.loads(text)

    # Normalize alternative formats to AggregatorConfig schema
    if isinstance(data, dict):
        # Array style: { "servers": [ { name, command, args?, env? } ] }
        if "servers" in data and isinstance(data["servers"], list):
            upstream: list[dict] = []
            for s in data["servers"]:
                if not isinstance(s, dict):
                    continue
                cmd = s.get("command")
                args = s.get("args")
                if isinstance(cmd, list):
                    command = cmd + (args or [])
                elif isinstance(cmd, str):
                    command = [cmd] + (args or [])
                else:
                    command = []
                upstream.append(
                    {
                        "name": s.get("name"),
                        "command": command,
                        "env": s.get("env", {}) or {},
                        "include_tools": s.get("include_tools"),
                        "exclude_tools": s.get("exclude_tools"),
                    }
                )
            data = {**data, "upstream": upstream}

        # Object style: { "mcpServers": { name: { command, args?, env? } } }
        if "mcpServers" in data and isinstance(data["mcpServers"], dict):
            upstream: list[dict] = data.get("upstream", []) or []
            for name, s in data["mcpServers"].items():
                if not isinstance(s, dict):
                    continue
                if s.get("disabled") is True:
                    continue
                cmd = s.get("command")
                args = s.get("args")
                if isinstance(cmd, list):
                    command = cmd + (args or [])
                elif isinstance(cmd, str):
                    command = [cmd] + (args or [])
                else:
                    command = []
                upstream.append(
                    {
                        "name": name,
                        "command": command,
                        "env": s.get("env", {}) or {},
                        "include_tools": (s.get("tools", {}) or {}).get("allowed"),
                    }
                )
            data = {k: v for k, v in data.items() if k != "mcpServers"}
            data["upstream"] = upstream

    try:
        cfg = AggregatorConfig.model_validate(data)
    except ValidationError as e:
        raise RuntimeError(f"Invalid configuration: {e}") from e
    return _apply_env_overrides(cfg)
