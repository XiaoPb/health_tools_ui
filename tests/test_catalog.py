from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from health_tools_ui.catalog import COMMAND_ORDER, REQUEST_TYPES, build_catalog, catalog_by_name


def test_catalog_contains_every_api_operation() -> None:
    catalog = build_catalog()
    assert tuple(spec.name for spec in catalog) == COMMAND_ORDER
    assert len(catalog) == 13


def test_catalog_fields_match_public_request_models() -> None:
    for spec in build_catalog():
        expected = {item.name for item in fields(REQUEST_TYPES[spec.name])}
        if spec.name == "config":
            expected -= {"source", "expected_revision"}
        assert {field.name for field in spec.fields} == expected


def test_catalog_has_no_cli_only_verbose_field() -> None:
    for command in build_catalog():
        assert "verbose" not in {field.name for field in command.fields}
        assert all(field.help and field.kind.value for field in command.fields)


def test_config_uses_single_action_field() -> None:
    config = catalog_by_name()["config"]
    fields_by_name = {field.name: field for field in config.fields}
    assert set(fields_by_name) == {"action", "value", "force"}
    assert {choice.value for choice in fields_by_name["action"].choices} == {
        "show",
        "init",
        "set_rules_dir",
        "set_offline_path",
        "set_offline_default",
        "scan_offline",
    }


def test_latest_offline_fields_are_exposed() -> None:
    fields_by_name = {field.name: field for field in catalog_by_name()["offline"].fields}
    assert fields_by_name["ppg_offset"].default == 0
    assert fields_by_name["ppg_maps"].multiple is True
    assert fields_by_name["settle_timeout"].default == 10


def test_ui_only_imports_health_tools_public_api() -> None:
    source_root = Path(__file__).parents[1] / "src" / "health_tools_ui"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    forbidden = (
        "health_tools.cli",
        "health_tools.commands",
        "health_tools.config",
        "health_tools.core",
        "health_tools.rules",
        "health_tools.utils",
    )
    assert not any(name in sources for name in forbidden)
