from __future__ import annotations

import io
import json
import time

from health_tools.api import BatchResult, OfflineResult

from health_tools_ui.runner import worker_command
from health_tools_ui.worker import run_offline_worker


def test_worker_rejects_invalid_protocol() -> None:
    output = io.StringIO()
    assert run_offline_worker(io.StringIO("[]\n"), output) == 2
    assert json.loads(output.getvalue())["error_type"] == "ProtocolError"


def test_worker_emits_structured_result(monkeypatch) -> None:
    monkeypatch.setattr("health_tools_ui.worker.build_request", lambda _command, values: values)
    monkeypatch.setattr(
        "health_tools_ui.worker.operation_runner",
        lambda _command: (
            lambda _request, context: OfflineResult(
                batch=__import__("health_tools.api", fromlist=["BatchResult"]).BatchResult(
                    "offline"
                )
            )
        ),
    )
    output = io.StringIO()
    assert (
        run_offline_worker(io.StringIO('{"type":"run","values":{"do_list":true}}\n'), output) == 0
    )
    message = json.loads(output.getvalue())
    assert message["type"] == "result"
    assert message["result"]["kind"] == "OfflineResult"


def test_worker_command_is_dedicated_offline_entrypoint() -> None:
    program, arguments = worker_command()
    assert program
    assert arguments[-1] == "--offline-worker"


def test_worker_accepts_cooperative_cancel(monkeypatch) -> None:
    monkeypatch.setattr("health_tools_ui.worker.build_request", lambda _command, values: values)

    def runner(_request, context):
        for _ in range(100):
            context.check_cancelled("run", BatchResult("offline"))
            time.sleep(0.001)
        return OfflineResult(BatchResult("offline"))

    monkeypatch.setattr("health_tools_ui.worker.operation_runner", lambda _command: runner)
    source = io.StringIO('{"type":"run","values":{}}\n{"type":"cancel"}\n')
    output = io.StringIO()
    assert run_offline_worker(source, output) == 0
    message = json.loads(output.getvalue())
    assert message["type"] == "cancelled"
    assert message["stage"] == "run"
