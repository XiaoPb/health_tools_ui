from __future__ import annotations

from pathlib import Path

from health_tools.api import ConfigAction, ParseRequest

from health_tools_ui.api_adapter import build_request
from health_tools_ui.arguments import is_dangerous, validate_values
from health_tools_ui.catalog import catalog_by_name


def test_unicode_paths_build_typed_request() -> None:
    request = build_request(
        "parse",
        {"input_path": "E:/健康 数据/raw.log", "output_path": "E:/输出/data.csv"},
    )
    assert request == ParseRequest(Path("E:/健康 数据/raw.log"), Path("E:/输出/data.csv"))


def test_required_values_are_reported() -> None:
    issues = validate_values(catalog_by_name()["parse"], {})
    assert {issue.path for issue in issues} >= {"input_path", "output_path"}


def test_classify_move_is_dangerous() -> None:
    spec = catalog_by_name()["classify"]
    values = {field.name: field.default for field in spec.fields}
    values.update({"input_path": "in", "output_path": "out", "mode": "move"})
    assert is_dangerous(spec, values)
    assert build_request("classify", values).mode == "move"


def test_config_action_maps_to_enum() -> None:
    request = build_request("config", {"action": "init", "force": True})
    assert request.action == ConfigAction.INIT
    assert request.force is True
