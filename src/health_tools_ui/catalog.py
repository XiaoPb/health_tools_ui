from __future__ import annotations

from collections import defaultdict
from typing import Any

import click
from health_tools.cli import main as health_main

from .models import CommandSpec, FieldChoice, FieldKind, FieldSpec

COMMAND_ORDER = (
    "parse",
    "plot",
    "classify",
    "convert",
    "info",
    "validate",
    "split",
    "process",
    "factory",
    "config",
    "evaluate",
    "offline",
    "check",
)

COMMAND_META: dict[str, tuple[str, str, str]] = {
    "parse": ("数据处理", "日志解析 Parse", "files"),
    "plot": ("分析评估", "数据绘图 Plot", "images"),
    "classify": ("数据处理", "数据分类 Classify", "files"),
    "convert": ("数据处理", "格式转换 Convert", "csv"),
    "info": ("分析评估", "文件信息 Info", "text"),
    "validate": ("质量与离线", "规则验证 Validate", "text"),
    "split": ("数据处理", "数据分割 Split", "files"),
    "process": ("数据处理", "批量处理 Process", "files"),
    "factory": ("分析评估", "产测计算 Factory", "csv"),
    "config": ("设置", "全局配置 Config", "text"),
    "evaluate": ("分析评估", "指标评估 Evaluate", "csv"),
    "offline": ("质量与离线", "离线跑库 Offline", "files"),
    "check": ("质量与离线", "数据检查 Check", "csv"),
}

PRIMARY_FIELDS: dict[str, set[str]] = {
    "parse": {"input_path", "output_path", "rule_file", "chip_name"},
    "plot": {"input_path", "output_path", "plot_type", "channels", "sample_rate"},
    "classify": {"input_path", "output_path", "rule_file", "mode"},
    "convert": {"input_path", "output_path", "rule_file", "chip_name", "init_rule"},
    "info": {"target", "stats", "preview", "schema"},
    "validate": {"rule_file", "strict"},
    "split": {"input_path", "output_path", "chip_name", "by_column", "by_size"},
    "process": {"input_path", "output_path", "chip_name", "frame_split", "max_workers"},
    "factory": {"input_path", "chip_name", "rule_file", "output_path"},
    "config": {"do_init", "do_show", "rules_dir", "offline_path", "offline_default"},
    "evaluate": {"input_path", "output_path", "eval_type", "chip", "rule_file"},
    "offline": {"input_path", "output_path", "chip_name", "ver", "versions", "do_list"},
    "check": {"input_path", "chip_name", "checks", "output_path", "sort_report"},
}

PATH_MODES: dict[str, str] = {
    "input_path": "any",
    "output_path": "save",
    "rule_file": "file",
    "target": "file",
    "rules_dir": "directory",
    "offline_path": "directory",
    "report_path": "file",
    "sort_output": "directory",
}

COMMAND_PATH_MODES: dict[tuple[str, str], str] = {
    ("parse", "output_path"): "save",
    ("plot", "output_path"): "directory",
    ("classify", "output_path"): "directory",
    ("convert", "output_path"): "directory",
    ("split", "output_path"): "directory",
    ("process", "output_path"): "directory",
    ("factory", "output_path"): "directory",
    ("evaluate", "output_path"): "directory",
    ("offline", "input_path"): "directory",
    ("offline", "output_path"): "directory",
}

CHOICE_PROVIDERS: dict[tuple[str, str], str] = {
    ("parse", "rule_file"): "parse",
    ("classify", "rule_file"): "classify",
    ("classify", "extend_files"): "classify_patterns",
    ("convert", "rule_file"): "convert",
    ("plot", "rule_file"): "convert",
    ("factory", "rule_file"): "convert",
    ("evaluate", "rule_file"): "evaluate",
    ("validate", "rule_file"): "all_rules",
}

DANGEROUS: dict[str, tuple[Any, ...]] = {
    "mode": ("move",),
    "sort_report": (True,),
    "do_force": (True,),
}


def _kind_for(param: click.Parameter) -> FieldKind:
    if (param.name or "") in PATH_MODES:
        return FieldKind.PATH
    if isinstance(param, click.Option) and param.is_flag:
        return FieldKind.BOOLEAN
    if isinstance(param.type, click.Path):
        return FieldKind.PATH
    if isinstance(param.type, click.Choice):
        return FieldKind.CHOICE
    if isinstance(param.type, click.types.IntParamType):
        return FieldKind.INTEGER
    if isinstance(param.type, click.types.FloatParamType):
        return FieldKind.NUMBER
    if getattr(param, "multiple", False):
        return FieldKind.LIST
    return FieldKind.TEXT


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _safe_default(value: Any) -> Any:
    if repr(value) == "Sentinel.UNSET":
        return None
    if isinstance(value, tuple):
        return list(value)
    return value


def _field_from_param(command_name: str, param: click.Parameter) -> FieldSpec:
    option = param if isinstance(param, click.Option) else None
    choices: tuple[FieldChoice, ...] = ()
    if isinstance(param.type, click.Choice):
        choices = tuple(FieldChoice(str(value), value) for value in param.type.choices)
    flags = tuple(option.opts) if option else ()
    false_flags = tuple(option.secondary_opts) if option else ()
    help_text = option.help or "" if option else "Positional argument"
    return FieldSpec(
        name=param.name or "value",
        label=_label(param.name or "value"),
        help=help_text,
        kind=_kind_for(param),
        flags=flags,
        false_flags=false_flags,
        positional=not isinstance(param, click.Option),
        required=param.required,
        default=_safe_default(param.default),
        choices=choices,
        multiple=getattr(param, "multiple", False),
        advanced=(param.name or "") not in PRIMARY_FIELDS[command_name],
        path_mode=COMMAND_PATH_MODES.get(
            (command_name, param.name or ""), PATH_MODES.get(param.name or "", "file")
        ),
        dangerous_values=DANGEROUS.get(param.name or "", ()),
        choice_provider=_choice_provider(command_name, param.name or ""),
        allow_browse=(command_name, param.name or "") in CHOICE_PROVIDERS,
    )


def _choice_provider(command_name: str, field_name: str) -> str:
    explicit = CHOICE_PROVIDERS.get((command_name, field_name))
    if explicit:
        return explicit
    if field_name in {"chip", "chip_name"}:
        return "offline_chips" if command_name == "offline" else "chip"
    return ""


def _merge_flag_value_fields(
    fields: list[FieldSpec], params: list[click.Parameter]
) -> list[FieldSpec]:
    grouped: dict[str, list[tuple[FieldSpec, click.Parameter]]] = defaultdict(list)
    for field, param in zip(fields, params, strict=True):
        grouped[field.name].append((field, param))

    merged: list[FieldSpec] = []
    for name, items in grouped.items():
        if len(items) == 1:
            merged.append(items[0][0])
            continue
        options = [param for _, param in items if isinstance(param, click.Option)]
        if options and all(option.is_flag and option.flag_value is not None for option in options):
            first = items[0][0]
            default = next(
                (field.default for field, _ in items if field.default not in (None, False)),
                first.default,
            )
            choices = tuple(
                FieldChoice(_label(option.opts[0].lstrip("-")), option.flag_value, option.opts[0])
                for option in options
            )
            merged.append(
                FieldSpec(
                    name=name,
                    label=_label(name),
                    help=" / ".join(option.help or "" for option in options),
                    kind=FieldKind.CHOICE,
                    default=default,
                    choices=choices,
                    advanced=first.advanced,
                    dangerous_values=DANGEROUS.get(name, ()),
                )
            )
        else:
            merged.extend(field for field, _ in items)
    return merged


def build_catalog() -> tuple[CommandSpec, ...]:
    context = click.Context(health_main)
    specs: list[CommandSpec] = []
    for name in COMMAND_ORDER:
        command = health_main.get_command(context, name)
        if command is None:
            raise RuntimeError(f"ghealth-tools command is unavailable: {name}")
        params = list(command.params)
        fields = [_field_from_param(name, param) for param in params]
        fields = _merge_flag_value_fields(fields, params)
        group, title, result_type = COMMAND_META[name]
        specs.append(
            CommandSpec(
                name=name,
                title=title,
                group=group,
                help=command.help or command.short_help or "",
                result_type=result_type,
                fields=tuple(fields),
            )
        )
    return tuple(specs)


def catalog_by_name() -> dict[str, CommandSpec]:
    return {spec.name: spec for spec in build_catalog()}
