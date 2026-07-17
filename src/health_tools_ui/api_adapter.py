from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from health_tools.api import (
    AnalyzeRequest,
    AnalyzeResult,
    BatchResult,
    CheckRequest,
    CheckResult,
    ClassifyRequest,
    ConfigAction,
    ConfigRequest,
    ConvertRequest,
    EvaluateRequest,
    FactoryRequest,
    InfoRequest,
    OfflineRequest,
    OfflineResult,
    ParseRequest,
    PlotRequest,
    ProcessRequest,
    SplitRequest,
    ValidateRequest,
    run_analyze,
    run_check,
    run_classify,
    run_config,
    run_convert,
    run_evaluate,
    run_factory,
    run_info,
    run_offline,
    run_parse,
    run_plot,
    run_process,
    run_split,
    run_validate,
)

Operation = tuple[type[Any], Callable[..., Any]]
OPERATIONS: dict[str, Operation] = {
    "analyze": (AnalyzeRequest, run_analyze),
    "parse": (ParseRequest, run_parse),
    "plot": (PlotRequest, run_plot),
    "classify": (ClassifyRequest, run_classify),
    "convert": (ConvertRequest, run_convert),
    "info": (InfoRequest, run_info),
    "validate": (ValidateRequest, run_validate),
    "split": (SplitRequest, run_split),
    "process": (ProcessRequest, run_process),
    "factory": (FactoryRequest, run_factory),
    "config": (ConfigRequest, run_config),
    "evaluate": (EvaluateRequest, run_evaluate),
    "offline": (OfflineRequest, run_offline),
    "check": (CheckRequest, run_check),
}
PATH_FIELDS = {"input_path", "output_path", "target", "report_path", "sort_output"}
TUPLE_FIELDS = {"extend_files", "ppg_maps", "focus"}


def build_request(command: str, values: Mapping[str, Any]) -> Any:
    request_type, _runner = OPERATIONS[command]
    kwargs: dict[str, Any] = {}
    for item in fields(request_type):
        name = item.name
        if command == "config" and name in {"source", "expected_revision"}:
            continue
        if name not in values:
            continue
        value = values.get(name)
        if command == "config" and name == "action":
            value = ConfigAction(str(value or "show"))
        elif command == "check" and name == "checks" and isinstance(value, (list, tuple)):
            value = ",".join(str(part) for part in value if str(part)) or None
        elif name in PATH_FIELDS or (command == "validate" and name == "rule_file"):
            value = Path(str(value)) if value not in (None, "") else None
        elif name in TUPLE_FIELDS:
            value = (
                tuple(value or ())
                if not isinstance(value, str)
                else tuple(part.strip() for part in value.split(",") if part.strip())
            )
        elif value == "":
            value = None
        kwargs[name] = value
    return request_type(**kwargs)


def operation_runner(command: str) -> Callable[..., Any]:
    return OPERATIONS[command][1]


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return value


def serialize_result(result: Any) -> dict[str, Any]:
    payload = to_jsonable(result)
    if not isinstance(payload, dict):
        payload = {"value": payload}
    payload["kind"] = type(result).__name__
    batch = (
        result.batch if isinstance(result, (AnalyzeResult, CheckResult, OfflineResult)) else result
    )
    if isinstance(batch, BatchResult):
        payload["counts"] = {
            "ok": batch.ok_count,
            "skip": batch.skip_count,
            "warn": batch.warn_count,
            "fail": batch.fail_count,
        }
    return payload


def result_has_failures(result: Mapping[str, Any] | None) -> bool:
    counts = result.get("counts", {}) if result else {}
    return bool(isinstance(counts, Mapping) and counts.get("fail", 0))


def result_artifacts(result: Mapping[str, Any] | None) -> list[str]:
    if not result:
        return []
    batch = result.get("batch") if isinstance(result.get("batch"), Mapping) else result
    values = batch.get("artifacts", []) if isinstance(batch, Mapping) else []
    return [str(value) for value in values]


def result_output(result: Mapping[str, Any] | None) -> str | None:
    artifacts = result_artifacts(result)
    if artifacts:
        return artifacts[0]
    if not result:
        return None
    for name in ("report_path", "output_dir"):
        value = result.get(name)
        if value:
            return str(value)
    return None
