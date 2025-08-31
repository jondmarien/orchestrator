from __future__ import annotations

from typing import Any


def make_request(id_: int | str, method: str, params: Any | None = None) -> dict:
    req = {
        "jsonrpc": "2.0",
        "id": id_,
        "method": method,
    }
    if params is not None:
        req["params"] = params
    return req


def make_response(id_: int | str, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def make_error(id_: int | str | None, code: int, message: str, data: Any | None = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err}
