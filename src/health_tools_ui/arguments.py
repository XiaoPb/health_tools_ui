from __future__ import annotations

from typing import Any

from .models import CommandSpec, FieldKind, FieldSpec, ValidationIssue


def validate_values(spec: CommandSpec, values: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field in spec.fields:
        value = values.get(field.name, field.default)
        if field.required and (value is None or value == "" or value == []):
            issues.append(
                ValidationIssue(
                    field.name,
                    "error",
                    f"{field.label} 为必填项",
                    f"{field.label} is required",
                )
            )
    return issues


def is_dangerous(spec: CommandSpec, values: dict[str, Any]) -> bool:
    return any(
        values.get(field.name, field.default) in field.dangerous_values
        for field in spec.fields
        if field.dangerous_values
    )


def _append_value(argv: list[str], field: FieldSpec, value: Any) -> None:
    if field.positional:
        argv.append(str(value))
        return

    if field.kind == FieldKind.CHOICE and any(choice.flag for choice in field.choices):
        choice = next((choice for choice in field.choices if choice.value == value), None)
        if choice and choice.flag:
            argv.append(choice.flag)
        return

    flag = field.flags[0] if field.flags else ""
    if field.kind == FieldKind.BOOLEAN:
        if bool(value) and not bool(field.default) and flag:
            argv.append(flag)
        elif not bool(value) and bool(field.default) and field.false_flags:
            argv.append(field.false_flags[0])
        return

    if field.multiple or field.kind == FieldKind.LIST:
        items = (
            value
            if isinstance(value, (list, tuple))
            else [item.strip() for item in str(value).split(",")]
        )
        for item in items:
            if item in (None, ""):
                continue
            if flag:
                argv.extend([flag, str(item)])
        return

    if flag:
        argv.extend([flag, str(value)])


def build_argv(
    spec: CommandSpec,
    values: dict[str, Any],
    log_level: str = "info",
) -> list[str]:
    argv = ["--log-level", log_level, spec.name]
    for field in spec.fields:
        value = values.get(field.name, field.default)
        if value is None or value == "" or value == []:
            continue
        if not field.required and value == field.default and field.kind != FieldKind.CHOICE:
            continue
        _append_value(argv, field, value)
    return argv
