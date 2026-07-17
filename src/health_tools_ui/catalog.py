from __future__ import annotations

from dataclasses import MISSING, fields
from typing import Any

from health_tools.api import (
    CheckRequest,
    ClassifyRequest,
    ConfigRequest,
    ConvertRequest,
    EvaluateRequest,
    FactoryRequest,
    InfoRequest,
    OfflineRequest,
    ParseRequest,
    PlotRequest,
    ProcessRequest,
    SplitRequest,
    ValidateRequest,
)

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
REQUEST_TYPES = {
    "parse": ParseRequest,
    "plot": PlotRequest,
    "classify": ClassifyRequest,
    "convert": ConvertRequest,
    "info": InfoRequest,
    "validate": ValidateRequest,
    "split": SplitRequest,
    "process": ProcessRequest,
    "factory": FactoryRequest,
    "config": ConfigRequest,
    "evaluate": EvaluateRequest,
    "offline": OfflineRequest,
    "check": CheckRequest,
}
COMMAND_META: dict[str, tuple[str, str, str, str]] = {
    "parse": ("数据处理", "日志解析 Parse", "files", "按规则将日志解析为 CSV"),
    "plot": ("分析评估", "数据绘图 Plot", "images", "生成时域图与频谱图"),
    "classify": ("数据处理", "数据分类 Classify", "files", "按规则复制、移动或链接文件"),
    "convert": ("数据处理", "格式转换 Convert", "csv", "转换或合并 CSV 数据"),
    "info": ("分析评估", "文件信息 Info", "text", "读取文件摘要、结构与预览"),
    "validate": ("质量与离线", "规则验证 Validate", "text", "验证 YAML 规则"),
    "split": ("数据处理", "数据分割 Split", "files", "按列、大小或时间分割 CSV"),
    "process": ("数据处理", "批量处理 Process", "files", "批量处理 CSV 数据"),
    "factory": ("分析评估", "产测计算 Factory", "csv", "计算产测指标"),
    "config": ("设置", "全局配置 Config", "text", "读取或修改全局配置"),
    "evaluate": ("分析评估", "指标评估 Evaluate", "csv", "生成算法指标评估报告"),
    "offline": ("质量与离线", "离线跑库 Offline", "files", "运行离线算法并整理结果"),
    "check": ("质量与离线", "数据检查 Check", "csv", "检查数据质量或按报告分拣"),
}
PRIMARY_FIELDS = {
    "parse": {"input_path", "output_path", "rule_file", "chip_name"},
    "plot": {"input_path", "output_path", "plot_type", "channels", "sample_rate"},
    "classify": {"input_path", "output_path", "rule_file", "mode"},
    "convert": {"input_path", "output_path", "rule_file", "chip_name", "init_rule"},
    "info": {"target", "stats", "preview", "schema"},
    "validate": {"rule_file", "strict"},
    "split": {"input_path", "output_path", "chip_name", "by_column", "by_size"},
    "process": {"input_path", "output_path", "chip_name", "frame_split", "max_workers"},
    "factory": {"input_path", "chip_name", "rule_file", "output_path"},
    "config": {"action", "value", "force"},
    "evaluate": {"input_path", "output_path", "eval_type", "chip", "rule_file"},
    "offline": {"input_path", "output_path", "chip_name", "ver", "versions", "no_run"},
    "check": {"input_path", "chip_name", "checks", "output_path", "sort_report"},
}
PATH_FIELDS = {"input_path", "output_path", "rule_file", "target", "report_path", "sort_output"}
TUPLE_FIELDS = {"extend_files", "ppg_maps"}
MULTI_CHOICE_FIELDS = {("check", "checks")}
INTEGER_FIELDS = {
    "sample_rate",
    "window",
    "dpi",
    "preview",
    "by_size",
    "max_workers",
    "split",
    "hba_fs",
    "scene_en",
    "ch_num",
    "ref_col",
    "ppg_offset",
    "timeout",
    "settle_timeout",
    "tolerance",
    "static_min",
    "workers",
    "ref_column_col",
    "pred_column_col",
}
NUMBER_FIELDS = {
    "overlap",
    "column_value",
    "by_time",
    "gain",
    "current",
    "adc_offset",
    "diff_threshold",
    "stale_minutes",
    "range_ratio",
    "frame_ratio",
    "center_ratio",
    "ipd_ratio",
    "acc_ratio",
    "timestamp_ratio",
    "timestamp_ms",
    "timestamp_fail_ratio",
}
BOOLEAN_FIELDS = {
    "dry_run",
    "remove_baseline",
    "freq_bpm",
    "no_show",
    "enable_accuracy",
    "report",
    "merge",
    "init_rule",
    "stats",
    "schema",
    "strict",
    "frame_split",
    "force",
    "all_versions",
    "no_accuracy",
    "no_plot",
    "no_run",
    "do_list",
    "acc_axis",
    "sort_report",
}
CHOICES: dict[tuple[str, str], tuple[Any, ...]] = {
    ("plot", "plot_type"): ("time", "freq", "stft", "psd", "ac", "fft", "both"),
    ("plot", "fmt"): ("png", "svg", "pdf"),
    ("plot", "baseline_method"): ("mean", "median"),
    ("plot", "psd_acc"): ("axis", "rms"),
    ("check", "checks"): ("range", "ipd", "frame", "center", "acc"),
    ("classify", "mode"): ("copy", "move", "symlink"),
    ("evaluate", "eval_type"): ("hr", "spo2"),
    ("config", "action"): (
        "show",
        "init",
        "set_rules_dir",
        "set_offline_path",
        "set_offline_default",
        "scan_offline",
    ),
}
CHOICE_PROVIDERS = {
    ("parse", "rule_file"): "parse",
    ("classify", "rule_file"): "classify",
    ("classify", "extend_files"): "classify_patterns",
    ("convert", "rule_file"): "convert",
    ("plot", "rule_file"): "convert",
    ("factory", "rule_file"): "convert",
    ("evaluate", "rule_file"): "evaluate",
    ("validate", "rule_file"): "all_rules",
}
DANGEROUS = {"mode": ("move",), "sort_report": (True,), "force": (True,)}
FIELD_HELP = {
    "input_path": "待处理的文件或目录",
    "output_path": "保存结果的文件或目录",
    "rule_file": "使用的 YAML 规则",
    "chip_name": "数据对应的芯片型号",
    "target": "需要读取信息的文件",
    "action": "选择一个配置操作",
    "value": "所选配置操作需要的值",
    "force": "初始化时覆盖已存在的内置规则",
    "filter_name": "仅处理文件名包含该文本的文件",
    "do_list": "只读取可用芯片和算法版本",
    "checks": "默认执行范围、Ipd、帧完整性、数据居中和 ACC 五项检查",
    "channels": "通道名；AC 可用分号分隔多组通道",
    "psd_acc": "PSD 的 ACC 聚合方式：分轴或 RMS",
}

CHOICE_LABELS: dict[tuple[str, str, Any], str] = {
    ("plot", "plot_type", "time"): "时域",
    ("plot", "plot_type", "freq"): "频域",
    ("plot", "plot_type", "stft"): "STFT",
    ("plot", "plot_type", "psd"): "PSD",
    ("plot", "plot_type", "ac"): "自相关",
    ("plot", "plot_type", "fft"): "FFT",
    ("plot", "plot_type", "both"): "组合",
    ("plot", "psd_acc", "axis"): "分轴",
    ("plot", "psd_acc", "rms"): "RMS",
    ("check", "checks", "range"): "范围",
    ("check", "checks", "ipd"): "Ipd",
    ("check", "checks", "frame"): "帧完整性",
    ("check", "checks", "center"): "数据居中",
    ("check", "checks", "acc"): "ACC",
}


def _default(item: Any) -> Any:
    if item.default is not MISSING:
        value = item.default
    elif item.default_factory is not MISSING:
        value = item.default_factory()
    else:
        return None
    return list(value) if isinstance(value, tuple) else value


def _kind(command: str, name: str) -> FieldKind:
    if (command, name) in CHOICES:
        return FieldKind.CHOICE
    if name in PATH_FIELDS:
        return FieldKind.PATH
    if name in BOOLEAN_FIELDS:
        return FieldKind.BOOLEAN
    if name in INTEGER_FIELDS:
        return FieldKind.INTEGER
    if name in NUMBER_FIELDS:
        return FieldKind.NUMBER
    if name in TUPLE_FIELDS:
        return FieldKind.LIST
    return FieldKind.TEXT


def _provider(command: str, name: str) -> str:
    explicit = CHOICE_PROVIDERS.get((command, name))
    if explicit:
        return explicit
    if name in {"chip", "chip_name"}:
        return "offline_chips" if command == "offline" else "chip"
    return ""


def build_catalog() -> tuple[CommandSpec, ...]:
    specs: list[CommandSpec] = []
    for command in COMMAND_ORDER:
        request_type = REQUEST_TYPES[command]
        request_fields = fields(request_type)
        if command == "config":
            request_fields = tuple(
                item for item in request_fields if item.name in {"action", "value", "force"}
            )
        ui_fields: list[FieldSpec] = []
        for item in request_fields:
            name = item.name
            provider = _provider(command, name)
            choices = tuple(
                FieldChoice(CHOICE_LABELS.get((command, name, value), str(value)), value)
                for value in CHOICES.get((command, name), ())
            )
            path_mode = "any" if name in {"input_path", "target"} else "file"
            if name == "output_path":
                path_mode = "save" if command == "parse" else "directory"
            elif name == "sort_output":
                path_mode = "directory"
            default = _default(item)
            if command == "config" and name == "action":
                default = "show"
            elif command == "check" and name == "checks":
                default = ["range", "ipd", "frame", "center", "acc"]
            ui_fields.append(
                FieldSpec(
                    name=name,
                    label=name.replace("_", " ").title(),
                    help=FIELD_HELP.get(name, "业务参数"),
                    kind=_kind(command, name),
                    required=item.default is MISSING and item.default_factory is MISSING,
                    default=default,
                    choices=choices,
                    multiple=name in TUPLE_FIELDS or (command, name) in MULTI_CHOICE_FIELDS,
                    advanced=name not in PRIMARY_FIELDS[command],
                    path_mode=path_mode,
                    dangerous_values=DANGEROUS.get(name, ()),
                    choice_provider=provider,
                    allow_browse=bool(provider),
                    visible_when=(("action", "init"),)
                    if command == "config" and name == "force"
                    else (),
                )
            )
        group, title, result_type, help_text = COMMAND_META[command]
        specs.append(CommandSpec(command, title, group, help_text, result_type, tuple(ui_fields)))
    return tuple(specs)


def catalog_by_name() -> dict[str, CommandSpec]:
    return {spec.name: spec for spec in build_catalog()}
