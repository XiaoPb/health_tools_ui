from __future__ import annotations

from health_tools_ui.arguments import build_argv, is_dangerous, validate_values
from health_tools_ui.catalog import catalog_by_name


def test_unicode_paths_are_single_arguments() -> None:
    spec = catalog_by_name()["parse"]
    values = {field.name: field.default for field in spec.fields}
    values.update({"input_path": "E:/健康 数据/raw.log", "output_path": "E:/输出/data.csv"})
    argv = build_argv(spec, values)
    assert "E:/健康 数据/raw.log" in argv
    assert "E:/输出/data.csv" in argv
    assert argv[:3] == ["--log-level", "info", "parse"]


def test_required_values_are_reported() -> None:
    spec = catalog_by_name()["parse"]
    issues = validate_values(spec, {})
    assert {issue.path for issue in issues} >= {"input_path", "output_path"}


def test_classify_move_is_dangerous_and_builds_flag() -> None:
    spec = catalog_by_name()["classify"]
    values = {field.name: field.default for field in spec.fields}
    values.update({"input_path": "in", "output_path": "out", "mode": "move"})
    assert is_dangerous(spec, values)
    assert "--move" in build_argv(spec, values)


def test_default_true_dual_flag_can_be_disabled() -> None:
    spec = catalog_by_name()["plot"]
    values = {field.name: field.default for field in spec.fields}
    values.update({"input_path": "in.csv", "output_path": "out", "remove_baseline": False})
    assert "--no-remove-baseline" in build_argv(spec, values)
