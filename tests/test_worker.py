from __future__ import annotations

import json

from health_tools_ui.runner import worker_command
from health_tools_ui.worker import run_worker


def test_worker_rejects_non_string_payload(capsys) -> None:
    assert run_worker(json.dumps(["info", 3])) == 2
    assert "JSON array" in capsys.readouterr().err


def test_worker_runs_help() -> None:
    assert run_worker(["--help"]) == 0


def test_worker_command_does_not_use_a_shell() -> None:
    program, arguments = worker_command(["info", "E:/a b/数据.csv"])
    assert program
    assert arguments[0:2] == ["-m", "health_tools_ui"]
    assert "E:/a b/数据.csv" in arguments[-1]
