from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .models import ValidationIssue

RULE_KINDS = ("chip", "parse", "classify", "convert", "evaluate", "config")

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "chip": ("version", "chip", "csv", "columns"),
    "parse": ("version", "regex", "columns"),
    "classify": ("version", "structure"),
    "convert": ("version",),
    "evaluate": ("type", "ref_column", "pred_column"),
    "config": (),
}


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 100
    return yaml


def detect_rule_kind(path: Path | None, data: Any) -> str:
    if path:
        lowered = [part.lower() for part in path.parts]
        for kind in RULE_KINDS:
            if kind in lowered:
                return kind
        if path.name.lower() == "config.yaml":
            return "config"
    if isinstance(data, dict):
        keys = set(data)
        if {"chip", "csv", "columns"} <= keys:
            return "chip"
        if {"regex", "columns"} <= keys:
            return "parse"
        if "column_mapping" in keys or {"source_columns", "target_columns"} <= keys:
            return "convert"
        if {"ref_column", "pred_column"} <= keys:
            return "evaluate"
        if "structure" in keys or "classify_rules" in keys:
            return "classify"
    return "config"


@dataclass(slots=True)
class RuleDocument:
    path: Path | None
    kind: str
    data: CommentedMap
    original_source: str
    dirty: bool = False

    @classmethod
    def from_source(
        cls, source: str, path: Path | None = None, kind: str | None = None
    ) -> RuleDocument:
        parsed = _yaml().load(source) if source.strip() else CommentedMap()
        if not isinstance(parsed, CommentedMap):
            raise ValueError("YAML root must be a mapping")
        return cls(path, kind or detect_rule_kind(path, parsed), parsed, source)

    @classmethod
    def load(cls, path: Path, kind: str | None = None) -> RuleDocument:
        return cls.from_source(path.read_text(encoding="utf-8"), path, kind)

    def source(self) -> str:
        stream = io.StringIO()
        _yaml().dump(self.data, stream)
        return stream.getvalue()

    def replace_source(self, source: str) -> list[ValidationIssue]:
        try:
            replacement = RuleDocument.from_source(source, self.path, self.kind)
        except Exception as exc:
            return [ValidationIssue("$", "error", "YAML 语法错误", "Invalid YAML syntax", str(exc))]
        self.data = replacement.data
        self.dirty = True
        return self.validate()

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for key in REQUIRED_KEYS.get(self.kind, ()):
            if key not in self.data:
                issues.append(
                    ValidationIssue(
                        key,
                        "error",
                        f"缺少必填字段: {key}",
                        f"Missing required field: {key}",
                    )
                )
        if self.kind == "convert":
            has_mapping = isinstance(self.data.get("column_mapping"), dict)
            has_pairs = "source_columns" in self.data and "target_columns" in self.data
            if not has_mapping and not has_pairs:
                issues.append(
                    ValidationIssue(
                        "column_mapping",
                        "error",
                        "转换规则需要列映射或源列/目标列",
                        "Convert rules require column_mapping or source/target columns",
                    )
                )
        issues.extend(self._upstream_validation())
        return _deduplicate_issues(issues)

    def _upstream_validation(self) -> list[ValidationIssue]:
        if self.kind not in {"chip", "parse", "classify", "convert"}:
            return []
        try:
            from health_tools.rules.validator import RuleValidator

            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / self.kind / "rule.yaml"
                path.parent.mkdir(parents=True)
                path.write_text(self.source(), encoding="utf-8")
                errors = RuleValidator.validate_file(path)
        except Exception as exc:
            return [
                ValidationIssue(
                    "$",
                    "error",
                    "上游规则验证器执行失败",
                    "Upstream rule validator failed",
                    str(exc),
                )
            ]
        return [ValidationIssue("$", "error", error, error, error) for error in errors]

    def visual_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        def walk(value: Any, path: list[str], depth: int) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = [*path, str(key)]
                    entries.append(_entry(child_path, key, child, depth))
                    if isinstance(child, (dict, list)):
                        walk(child, child_path, depth + 1)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    child_path = [*path, str(index)]
                    entries.append(_entry(child_path, index, child, depth))
                    if isinstance(child, (dict, list)):
                        walk(child, child_path, depth + 1)

        walk(self.data, [], 0)
        return entries

    def set_value(self, pointer: str, value_source: str) -> None:
        parent, token = self._resolve_parent(pointer)
        value = _parse_value(value_source)
        if isinstance(parent, list):
            parent[int(token)] = value
        else:
            parent[token] = value
        self.dirty = True

    def add_child(self, pointer: str, key: str, value_source: str) -> None:
        target = self._resolve(pointer) if pointer else self.data
        value = _parse_value(value_source)
        if isinstance(target, list):
            target.append(value)
        elif isinstance(target, dict):
            if not key:
                raise ValueError("A mapping key is required")
            if key in target:
                raise ValueError(f"Key already exists: {key}")
            target[key] = value
        else:
            raise ValueError("Children can only be added to mappings and lists")
        self.dirty = True

    def remove(self, pointer: str) -> None:
        parent, token = self._resolve_parent(pointer)
        if isinstance(parent, list):
            del parent[int(token)]
        else:
            del parent[token]
        self.dirty = True

    def save(self, target: Path | None = None, overwrite: bool = False) -> Path:
        destination = target or self.path
        if destination is None:
            raise ValueError("A destination path is required")
        if destination.exists() and destination != self.path and not overwrite:
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.source()
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(source)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        self.path = destination
        self.original_source = source
        self.dirty = False
        return destination

    def _resolve(self, pointer: str) -> Any:
        current: Any = self.data
        for token in _tokens(pointer):
            current = current[int(token)] if isinstance(current, list) else current[token]
        return current

    def _resolve_parent(self, pointer: str) -> tuple[Any, str]:
        tokens = _tokens(pointer)
        if not tokens:
            raise ValueError("The document root cannot be replaced or removed")
        current: Any = self.data
        for token in tokens[:-1]:
            current = current[int(token)] if isinstance(current, list) else current[token]
        return current, tokens[-1]


def _parse_value(source: str) -> Any:
    if not source.strip():
        return ""
    parsed = _yaml().load(source)
    return parsed


def _tokens(pointer: str) -> list[str]:
    if not pointer:
        return []
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer.lstrip("/").split("/")]


def _pointer(tokens: list[str]) -> str:
    return "/" + "/".join(token.replace("~", "~0").replace("/", "~1") for token in tokens)


def _entry(path: list[str], key: Any, value: Any, depth: int) -> dict[str, Any]:
    if isinstance(value, dict):
        display = f"{{{len(value)} fields}}"
        kind = "mapping"
    elif isinstance(value, list):
        display = f"[{len(value)} items]"
        kind = "list"
    elif value is None:
        display = "null"
        kind = "scalar"
    elif isinstance(value, bool):
        display = "true" if value else "false"
        kind = "scalar"
    else:
        display = str(value)
        kind = "scalar"
    return {
        "pointer": _pointer(path),
        "key": str(key),
        "value": display,
        "kind": kind,
        "depth": depth,
        "editable": kind == "scalar",
    }


def _deduplicate_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    result: list[ValidationIssue] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        key = (issue.path, issue.raw or issue.message_en)
        if key not in seen:
            result.append(issue)
            seen.add(key)
    return result
