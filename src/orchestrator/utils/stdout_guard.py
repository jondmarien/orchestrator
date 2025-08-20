from __future__ import annotations

import contextlib
import logging
import os
import sys


class StdoutGuard(contextlib.AbstractContextManager):
    """
    Redirect all logging and print-style output away from stdout while active.

    - stdout is reserved exclusively for JSON-RPC payloads
    - logs go to stderr
    """

    def __init__(self) -> None:
        self._orig_stdout = sys.stdout
        # Configure root logger only once
        if not logging.getLogger().handlers:
            logging.basicConfig(
                stream=sys.stderr,
                level=os.environ.get("ORCH_LOG_LEVEL", "INFO"),
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )

    def __enter__(self) -> StdoutGuard:
        sys.stdout = sys.__stdout__  # ensure stdout is the real stdout
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        sys.stdout = self._orig_stdout
        return False
