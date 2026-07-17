from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class FieldKind(StrEnum):
    TEXT = "text"
    PATH = "path"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    LIST = "list"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class FieldChoice:
    label: str
    value: Any
    flag: str | None = None


@dataclass(slots=True)
class FieldSpec:
    name: str
    label: str
    help: str
    kind: FieldKind
    flags: tuple[str, ...] = ()
    false_flags: tuple[str, ...] = ()
    positional: bool = False
    required: bool = False
    default: Any = None
    choices: tuple[FieldChoice, ...] = ()
    multiple: bool = False
    advanced: bool = False
    path_mode: str = "file"
    dangerous_values: tuple[Any, ...] = ()
    choice_provider: str = ""
    allow_browse: bool = False
    visible_when: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        return result


@dataclass(slots=True)
class CommandSpec:
    name: str
    title: str
    group: str
    help: str
    result_type: str
    fields: tuple[FieldSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "group": self.group,
            "help": self.help,
            "resultType": self.result_type,
            "fields": [field.to_dict() for field in self.fields],
        }


@dataclass(slots=True)
class JobRequest:
    command: str
    argv: list[str]
    values: dict[str, Any]
    output_path: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(slots=True)
class JobRecord:
    request: JobRequest
    status: JobStatus = JobStatus.QUEUED
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    log: str = ""
    stage: str = ""
    completed: int = 0
    total: int | None = None
    message: str = ""
    result: dict[str, Any] | None = None
    error_type: str = ""
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request.id,
            "command": self.request.command,
            "argv": self.request.argv,
            "values": self.request.values,
            "outputPath": self.request.output_path or "",
            "status": self.status.value,
            "createdAt": self.request.created_at,
            "startedAt": self.started_at or "",
            "finishedAt": self.finished_at or "",
            "exitCode": self.exit_code if self.exit_code is not None else -1,
            "log": self.log,
            "stage": self.stage,
            "completed": self.completed,
            "total": self.total if self.total is not None else -1,
            "message": self.message,
            "percent": round(self.completed * 100 / self.total, 1) if self.total else -1,
            "result": self.result or {},
            "errorType": self.error_type,
            "errorMessage": self.error_message,
        }


@dataclass(slots=True)
class ValidationIssue:
    path: str
    severity: str
    message_zh: str
    message_en: str
    raw: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
