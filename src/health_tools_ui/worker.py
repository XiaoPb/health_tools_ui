from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence

import click
from health_tools.cli import main as health_main


def run_worker(payload: str | Sequence[str]) -> int:
    argv = json.loads(payload) if isinstance(payload, str) else list(payload)
    if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
        print("Worker payload must be a JSON array of strings", file=sys.stderr)
        return 2

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    try:
        health_main.main(args=argv, prog_name="ghealth_tool", standalone_mode=False)
        return 0
    except click.ClickException as exc:
        exc.show(file=sys.stderr)
        return int(getattr(exc, "exit_code", 1))
    except click.Abort as exc:
        print("Aborted!", file=sys.stderr)
        return int(getattr(exc, "exit_code", 1))
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
