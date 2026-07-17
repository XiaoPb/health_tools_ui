from __future__ import annotations

from typing import Any

from .models import CommandSpec, ValidationIssue


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
