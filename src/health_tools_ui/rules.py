from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .models import ValidationIssue
from .rule_schema import RuleSchemaRegistry

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
    source_buffer: str | None = None

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

    def editor_source(self) -> str:
        return self.source_buffer if self.source_buffer is not None else self.source()

    @property
    def variant(self) -> str:
        if self.kind == "classify" and "patterns" in self.data:
            main_keys = {"structure", "classify", "rules", "extract"}
            if not (main_keys & set(self.data)):
                return "patterns"
        return self.kind

    def replace_source(self, source: str) -> list[ValidationIssue]:
        if source == self.editor_source():
            return []
        try:
            replacement = RuleDocument.from_source(source, self.path, self.kind)
        except Exception as exc:
            self.source_buffer = source
            self.dirty = True
            return [ValidationIssue("$", "error", "YAML 语法错误", "Invalid YAML syntax", str(exc))]
        self.data = replacement.data
        self.source_buffer = None
        self.dirty = True
        return self.validate()

    def validate(self) -> list[ValidationIssue]:
        if self.source_buffer is not None:
            try:
                RuleDocument.from_source(self.source_buffer, self.path, self.kind)
            except Exception as exc:
                return [
                    ValidationIssue(
                        "$", "error", "YAML 语法错误", "Invalid YAML syntax", str(exc)
                    )
                ]
        issues: list[ValidationIssue] = []
        required_keys = REQUIRED_KEYS.get(self.kind, ())
        if self.kind == "parse" and isinstance(self.data.get("patterns"), dict):
            required_keys = ("version", "patterns")
        if self.variant == "patterns":
            required_keys = ("version", "patterns")
        for key in required_keys:
            if key not in self.data:
                issues.append(
                    ValidationIssue(
                        key,
                        "error",
                        f"缺少必填字段: {key}",
                        f"Missing required field: {key}",
                    )
                )
        issues.extend(_validate_schema_types(self.kind, self.variant, self.data))
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
        if self.variant == "patterns" or (
            self.kind == "parse" and isinstance(self.data.get("patterns"), dict)
        ):
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

    def tree_nodes(self) -> list[dict[str, Any]]:
        def nodes(value: Any, path: list[str]) -> list[dict[str, Any]]:
            items = (
                value.items()
                if isinstance(value, dict)
                else enumerate(value)
                if isinstance(value, list)
                else []
            )
            result: list[dict[str, Any]] = []
            for key, child in items:
                child_path = [*path, str(key)]
                entry = _entry(child_path, key, child, len(path))
                node = {
                    **entry,
                    "title": f"{entry['key']}: {entry['value']}",
                    "key": entry["pointer"],
                }
                if isinstance(child, (dict, list)):
                    node["children"] = nodes(child, child_path)
                result.append(node)
            return result

        return nodes(self.data, [])

    def node(self, pointer: str) -> dict[str, Any]:
        if not pointer:
            return {
                "pointer": "",
                "key": "$",
                "value": "root",
                "kind": "mapping",
                "editable": False,
            }
        parent, token = self._resolve_parent(pointer)
        value = parent[int(token)] if isinstance(parent, list) else parent[token]
        return _entry(_tokens(pointer), token, value, len(_tokens(pointer)) - 1)

    def available_keys(self, pointer: str) -> list[dict[str, Any]]:
        target = self._resolve(pointer) if pointer else self.data
        if not isinstance(target, dict):
            return []
        schemas = RuleSchemaRegistry.available_children(
            self.kind, pointer, set(str(key) for key in target), self.variant
        )
        return [schema.to_choice() for schema in schemas]

    def add_suggested(self, pointer: str, key: str) -> None:
        candidates = {
            item.key: item
            for item in RuleSchemaRegistry.available_children(
                self.kind,
                pointer,
                set((self._resolve(pointer) if pointer else self.data).keys()),
                self.variant,
            )
        }
        if key not in candidates:
            raise ValueError(f"当前位置不支持字段: {key}")
        self.add_child(pointer, key, _dump_value(candidates[key].default))

    def add_list_item(self, pointer: str) -> None:
        target = self._resolve(pointer)
        if not isinstance(target, list):
            raise ValueError("只能向列表添加项目")
        schema = RuleSchemaRegistry.schema_at(self.kind, pointer, self.variant)
        template = schema.item_template if schema is not None else ""
        target.append(template if not isinstance(template, (dict, list)) else _clone(template))
        self.dirty = True

    def move_list_item(self, pointer: str, offset: int) -> None:
        parent, token = self._resolve_parent(pointer)
        if not isinstance(parent, list):
            raise ValueError("只能调整列表项目顺序")
        index = int(token)
        destination = index + offset
        if destination < 0 or destination >= len(parent):
            return
        parent[index], parent[destination] = parent[destination], parent[index]
        self.dirty = True

    def apply_inferred_columns(self, columns: list[str]) -> None:
        if self.kind == "parse":
            self.data["columns"] = CommentedSeq(columns)
        elif self.kind == "convert":
            existing = self.data.get("column_mapping", {})
            existing = existing if isinstance(existing, dict) else {}
            self.data["column_mapping"] = CommentedMap(
                (column, existing.get(column, column)) for column in columns
            )
        else:
            raise ValueError("CSV 列推断仅支持 parse 和 convert 规则")
        self.dirty = True

    def set_value(self, pointer: str, value_source: str) -> bool:
        parent, token = self._resolve_parent(pointer)
        value = _parse_value(value_source)
        current = parent[int(token)] if isinstance(parent, list) else parent[token]
        if _same_value(current, value):
            return False
        if isinstance(parent, list):
            parent[int(token)] = value
        else:
            parent[token] = value
        self.dirty = True
        return True

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
        self.source_buffer = None
        return destination

    def has_external_changes(self, target: Path | None = None) -> bool:
        destination = target or self.path
        if destination is None:
            return False
        try:
            return destination.read_text(encoding="utf-8") != self.original_source
        except OSError:
            return True

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


def _same_value(left: Any, right: Any) -> bool:
    return _value_kind(left) == _value_kind(right) and left == right


def _value_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def _dump_value(value: Any) -> str:
    stream = io.StringIO()
    _yaml().dump(value, stream)
    return stream.getvalue().strip() or "null"


def _clone(value: Any) -> Any:
    return _parse_value(_dump_value(value))


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
        "rawValue": value if kind == "scalar" else None,
        "valueType": "boolean"
        if isinstance(value, bool)
        else "number"
        if isinstance(value, (int, float))
        else "text",
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


def _validate_schema_types(kind: str, variant: str, data: Any) -> list[ValidationIssue]:
    expected_types: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "mapping": dict,
        "list": list,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "text": str,
        "regex": str,
        "choice": str,
        "path": str,
    }
    issues: list[ValidationIssue] = []
    for schema in RuleSchemaRegistry.fields(kind, variant):
        if schema.key not in data:
            continue
        expected = expected_types.get(schema.kind)
        value = data[schema.key]
        if expected is not None and not isinstance(value, expected):
            issues.append(
                ValidationIssue(
                    schema.key,
                    "error",
                    f"字段 {schema.key} 类型应为 {schema.kind}",
                    f"Field {schema.key} must be {schema.kind}",
                )
            )
    return issues
