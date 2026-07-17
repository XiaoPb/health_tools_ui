from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RuleDiagnostic:
    severity: str
    code: str
    message: str
    pointer: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "pointer": self.pointer,
        }


@dataclass(frozen=True, slots=True)
class CsvProfile:
    path: Path
    encoding: str
    delimiter: str
    info_row: int
    header_row: int
    data_start_row: int
    columns: tuple[str, ...]
    column_types: tuple[str, ...]
    preview: tuple[tuple[str, ...], ...]
    sampled_rows: int
    width_mismatches: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "encoding": self.encoding,
            "delimiter": "TAB" if self.delimiter == "\t" else self.delimiter,
            "infoRow": self.info_row,
            "headerRow": self.header_row,
            "dataStartRow": self.data_start_row,
            "columns": list(self.columns),
            "columnTypes": list(self.column_types),
            "preview": [list(row) for row in self.preview],
            "sampledRows": self.sampled_rows,
            "widthMismatches": self.width_mismatches,
        }


@dataclass(frozen=True, slots=True)
class LogGroupCandidate:
    component: str
    marker: str
    grammar: str
    field_count: int
    count: int
    columns: tuple[str, ...]
    samples: tuple[str, ...]
    anomaly_count: int = 0
    anomaly_samples: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.component}:{self.marker}:{self.grammar}:{self.field_count}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "component": self.component,
            "marker": self.marker,
            "grammar": self.grammar,
            "fieldCount": self.field_count,
            "count": self.count,
            "columns": list(self.columns),
            "sample": self.samples[0] if self.samples else "",
            "anomalyCount": self.anomaly_count,
        }


@dataclass(frozen=True, slots=True)
class ColumnMappingDraft:
    source: str
    target: str
    enabled: bool = True
    matched: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.source,
            "source": self.source,
            "target": self.target,
            "enabled": self.enabled,
            "status": "已匹配" if self.matched else "未匹配",
        }


@dataclass(frozen=True, slots=True)
class ChipColumnGroup:
    name: str
    columns: tuple[str, ...]
    role: str = "data"
    compact: str = ""

    @property
    def rule_value(self) -> str | tuple[str, ...]:
        return self.compact or self.columns

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.name,
            "name": self.name,
            "columns": list(self.columns),
            "display": self.compact or ", ".join(self.columns),
            "count": len(self.columns),
            "role": self.role,
        }


@dataclass(slots=True)
class RuleDraft:
    kind: str
    name: str
    source: str
    diagnostics: list[RuleDiagnostic] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == "error" for item in self.diagnostics)

    @property
    def has_warnings(self) -> bool:
        return any(item.severity == "warning" for item in self.diagnostics)
