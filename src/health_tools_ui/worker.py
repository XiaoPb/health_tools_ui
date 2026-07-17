from __future__ import annotations

import json
import sys
from threading import Event, Thread
from typing import Any, TextIO

from health_tools.api import ExecutionContext, GHealthError, OperationCancelled

from .api_adapter import build_request, operation_runner, serialize_result, to_jsonable


def _write(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def run_offline_worker(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    source = stdin or sys.stdin
    target = stdout or sys.stdout
    first = source.readline()
    try:
        message = json.loads(first)
    except (json.JSONDecodeError, TypeError):
        _write(
            target,
            {"type": "error", "error_type": "ProtocolError", "message": "Invalid run message"},
        )
        return 2
    if not isinstance(message, dict) or message.get("type") != "run":
        _write(
            target,
            {"type": "error", "error_type": "ProtocolError", "message": "Expected run message"},
        )
        return 2

    cancelled = Event()

    def read_control() -> None:
        for line in source:
            try:
                control = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(control, dict) and control.get("type") == "cancel":
                cancelled.set()
                return

    Thread(target=read_control, daemon=True).start()

    def on_progress(event: Any) -> None:
        _write(target, {"type": "progress", "event": to_jsonable(event)})

    try:
        request = build_request("offline", message.get("values", {}))
        result = operation_runner("offline")(
            request,
            context=ExecutionContext(on_progress=on_progress, is_cancelled=cancelled.is_set),
        )
        _write(target, {"type": "result", "result": serialize_result(result)})
        return 0
    except OperationCancelled as exc:
        partial = serialize_result(exc.partial_result) if exc.partial_result is not None else None
        _write(target, {"type": "cancelled", "stage": exc.stage, "result": partial})
        return 0
    except GHealthError as exc:
        _write(target, {"type": "error", "error_type": type(exc).__name__, "message": str(exc)})
        return 1
    except Exception as exc:
        _write(target, {"type": "error", "error_type": type(exc).__name__, "message": str(exc)})
        return 1


def run_worker(payload: str | list[str]) -> int:
    del payload
    print("Legacy CLI workers are no longer supported", file=sys.stderr)
    return 2
