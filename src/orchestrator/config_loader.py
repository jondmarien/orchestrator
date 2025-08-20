from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from orchestrator.config import AggregatorConfig


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
    try:
        return AggregatorConfig.model_validate(data)
    except ValidationError as e:
        raise RuntimeError(f"Invalid configuration: {e}") from e
