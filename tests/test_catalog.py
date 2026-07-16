from __future__ import annotations

import click
from health_tools.cli import main as health_main

from health_tools_ui.catalog import COMMAND_ORDER, build_catalog, catalog_by_name


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


def test_catalog_preserves_complete_click_parameter_contract() -> None:
    context = click.Context(health_main)
    for spec in build_catalog():
        command = health_main.get_command(context, spec.name)
        assert command is not None
        click_params: dict[str, list[click.Parameter]] = {}
        for parameter in command.params:
            click_params.setdefault(parameter.name or "", []).append(parameter)
        for field in spec.fields:
            parameters = click_params[field.name]
            parameter = parameters[0]
            assert field.required == parameter.required
            assert field.multiple == parameter.multiple
            if isinstance(parameter, click.Option):
                if len(parameters) == 1:
                    assert field.flags == tuple(parameter.opts)
                    assert field.false_flags == tuple(parameter.secondary_opts)
                else:
                    expected = {
                        option.opts[0]
                        for option in parameters
                        if isinstance(option, click.Option)
                    }
                    actual = {choice.flag for choice in field.choices}
                    assert actual == expected


def test_latest_offline_options_are_exposed() -> None:
    offline = catalog_by_name()["offline"]
    fields = {field.name: field for field in offline.fields}

    assert fields["ppg_offset"].flags == ("--ppg-offset",)
    assert fields["ppg_offset"].default == 0
    assert fields["ppg_maps"].flags == ("--ppg-map",)
    assert fields["ppg_maps"].multiple is True
    assert fields["settle_timeout"].flags == ("--settle-timeout",)
    assert fields["settle_timeout"].default == 10
