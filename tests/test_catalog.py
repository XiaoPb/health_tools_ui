from __future__ import annotations

import click
from health_tools.cli import main as health_main

from health_tools_ui.catalog import COMMAND_ORDER, build_catalog


def test_catalog_contains_every_business_command() -> None:
    catalog = build_catalog()
    assert tuple(spec.name for spec in catalog) == COMMAND_ORDER
    assert len(catalog) == 13


def test_catalog_parameter_names_match_click() -> None:
    context = click.Context(health_main)
    for spec in build_catalog():
        command = health_main.get_command(context, spec.name)
        assert command is not None
        click_names = {parameter.name for parameter in command.params}
        spec_names = {field.name for field in spec.fields}
        assert spec_names == click_names, spec.name


def test_every_field_has_help_and_input_kind() -> None:
    for command in build_catalog():
        for field in command.fields:
            assert field.name
            assert field.kind.value
            assert field.positional or field.flags or field.choices
