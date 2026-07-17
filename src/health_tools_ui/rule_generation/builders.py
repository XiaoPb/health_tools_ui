from __future__ import annotations

import io
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from health_tools.api import (
    ConvertRequest,
    RuleListRequest,
    RuleReadRequest,
    RuleType,
    run_convert,
    run_list_rules,
    run_read_rule,
)
from ruamel.yaml import YAML

from .models import (
    ChipColumnGroup,
    ColumnMappingDraft,
    CsvProfile,
    LogGroupCandidate,
    RuleDiagnostic,
    RuleDraft,
)

COMMON_CHIP_TEMPLATES: tuple[ChipColumnGroup, ...] = (
    ChipColumnGroup("时间", ("TimeStamp",), "time"),
    ChipColumnGroup("帧号", ("FRAME_ID",), "frame"),
    ChipColumnGroup("ACC", ("ACCX", "ACCY", "ACCZ"), "acc"),
    ChipColumnGroup(
        "算法输出", tuple(f"ALGO_RESULT{i}" for i in range(16)), "algorithm", "ALGO_RESULT{0-15}"
    ),
    ChipColumnGroup(
        "参考值", tuple(f"REF_RESULT{i}" for i in range(16)), "reference", "REF_RESULT{0-15}"
    ),
    ChipColumnGroup("AGC", tuple(f"AGC_INFO_CH{i}" for i in range(32)), "agc", "AGC_INFO_CH{0-31}"),
    ChipColumnGroup("Rawdata", tuple(f"Rawdata{i}" for i in range(32)), "factory", "Rawdata{0-31}"),
    ChipColumnGroup("Ipd", tuple(f"Ipd{i}" for i in range(32)), "ipd", "Ipd{0-31}"),
    ChipColumnGroup("CH", tuple(f"CH{i}" for i in range(32)), "factory", "CH{0-31}"),
)


def build_parse_rule(
    candidates: Sequence[LogGroupCandidate],
    *,
    name: str = "generated_parse.yaml",
    chip: str = "",
) -> RuleDraft:
    if not candidates:
        return RuleDraft(
            "parse",
            name,
            "version: '1.0'\npatterns: {}\n",
            [RuleDiagnostic("error", "no_patterns", "至少选择一个日志分组")],
        )
    patterns: dict[str, dict[str, Any]] = {}
    used: set[str] = set()
    diagnostics: list[RuleDiagnostic] = []
    for candidate in candidates:
        pattern_name = _unique_name(candidate.marker.lower(), used)
        used.add(pattern_name)
        marker = re.escape(candidate.marker)
        if candidate.grammar == "key_value":
            parts = [rf"{re.escape(column)}\s*:\s*([^,\s]+)" for column in candidate.columns]
            regex = rf".*\[{marker}\]\s*" + r",\s*".join(parts) + r"\s*$"
            patterns[pattern_name] = {"regex": regex, "columns": list(candidate.columns)}
        else:
            patterns[pattern_name] = {
                "regex": rf".*\[{marker}\]\s*,?\s*(.+)$",
                "columns": list(candidate.columns),
                "separator": ",",
            }
        if candidate.anomaly_count:
            diagnostics.append(
                RuleDiagnostic(
                    "warning",
                    "anomaly_samples",
                    f"{candidate.marker} 有 {candidate.anomaly_count} 条截断或控制字符"
                    "异常样本，已排除",
                    f"/patterns/{pattern_name}",
                )
            )
    data: dict[str, Any] = dict((("version", "1.0"), ("description", "由日志样本生成")))
    if chip:
        data["chip"] = chip
    data["patterns"] = patterns
    return RuleDraft("parse", name, _dump_yaml(data), diagnostics)


def build_chip_rule(
    profile: CsvProfile,
    chip_name: str,
    groups: Sequence[ChipColumnGroup],
    *,
    name: str | None = None,
) -> RuleDraft:
    if not chip_name.strip():
        return RuleDraft(
            "chip",
            name or "new_chip.yaml",
            "{}\n",
            [RuleDiagnostic("error", "chip_name", "请输入芯片名称")],
        )
    values: list[str] = []
    expanded: list[str] = []
    for group in groups:
        expanded.extend(group.columns)
        if group.compact:
            values.append(group.compact)
        else:
            values.extend(group.columns)
    diagnostics: list[RuleDiagnostic] = []
    missing = [column for column in expanded if column not in profile.columns]
    unused = [column for column in profile.columns if column not in expanded]
    if missing:
        diagnostics.append(
            RuleDiagnostic(
                "warning", "sample_missing", f"规则比样本多 {len(missing)} 列，保存前需确认"
            )
        )
    if unused:
        diagnostics.append(
            RuleDiagnostic("warning", "sample_unused", f"样本中有 {len(unused)} 列尚未加入规则")
        )
    data: dict[str, Any] = dict(
        (
            ("version", "1.0"),
            ("chip", chip_name.strip()),
            (
                "csv",
                dict(
                    (
                        ("info_row", profile.info_row),
                        ("header_row", profile.header_row),
                        ("data_start_row", profile.data_start_row),
                        ("delimiter", profile.delimiter),
                        ("encoding", profile.encoding),
                    )
                ),
            ),
            ("columns", values),
        )
    )
    roles = _role_config(groups, expanded)
    data.update(roles)
    return RuleDraft("chip", name or f"{chip_name}.yaml", _dump_yaml(data), diagnostics)


def initialize_convert_mapping(
    source_csv: Path, target_chip: str
) -> tuple[ColumnMappingDraft, ...]:
    with tempfile.TemporaryDirectory(prefix="health-tools-ui-convert-") as temp_dir:
        rule_path = Path(temp_dir) / "convert.yaml"
        run_convert(ConvertRequest(source_csv, rule_path, chip_name=target_chip, init_rule=True))
        data = YAML(typ="safe").load(rule_path.read_text(encoding="utf-8")) or {}
    mapping = data.get("column_mapping", {})
    if not isinstance(mapping, dict):
        return ()
    return tuple(
        ColumnMappingDraft(
            str(source), str(target), str(target) != "Unknown", str(target) != "Unknown"
        )
        for source, target in mapping.items()
    )


def render_convert_rule(
    profile: CsvProfile,
    target_chip: str,
    mappings: Sequence[ColumnMappingDraft],
    *,
    name: str = "generated_convert.yaml",
    forward_fill: Iterable[str] = (),
    expand_repeat: Mapping[str, int] | None = None,
) -> RuleDraft:
    active = [item for item in mappings if item.enabled]
    mapping = dict((item.source, item.target) for item in active if item.target)
    diagnostics: list[RuleDiagnostic] = []
    unmatched = [item.source for item in active if not item.matched or not item.target]
    if unmatched:
        diagnostics.append(
            RuleDiagnostic("warning", "unmapped_columns", f"{len(unmatched)} 个源列尚未匹配")
        )
    target_columns = load_chip_columns(target_chip)
    mapped_targets = set(mapping.values())
    missing_targets = [column for column in target_columns if column not in mapped_targets]
    if missing_targets:
        diagnostics.append(
            RuleDiagnostic(
                "warning",
                "zero_filled_targets",
                f"目标芯片有 {len(missing_targets)} 列未提供，转换时将补 0",
            )
        )
    data: dict[str, Any] = dict(
        (
            ("version", "1.0"),
            ("description", f"转换为 {target_chip} 格式"),
            ("target_chip", target_chip),
            (
                "csv",
                dict(
                    (
                        ("info_row", profile.info_row),
                        ("header_row", profile.header_row),
                        ("data_start_row", profile.data_start_row),
                        ("delimiter", profile.delimiter),
                        ("encoding", profile.encoding),
                    )
                ),
            ),
            ("column_mapping", mapping),
        )
    )
    fills = [value for value in forward_fill if value]
    if fills:
        data["forward_fill"] = fills
    if expand_repeat:
        data["expand_repeat"] = dict(expand_repeat)
    return RuleDraft(
        "convert", name, _dump_yaml(data), diagnostics, {"missingTargets": missing_targets}
    )


def build_classify_rule(
    keywords: Mapping[str, Sequence[str]],
    intervals: Sequence[tuple[str, float | None, float | None]] = (),
    *,
    value_column: str = "",
    name: str = "generated_classify.yaml",
) -> RuleDraft:
    clean_keywords = dict(
        (category, [word.strip() for word in words if word.strip()])
        for category, words in keywords.items()
        if category.strip()
    )
    clean_keywords = dict((key, values) for key, values in clean_keywords.items() if values)
    diagnostics: list[RuleDiagnostic] = []
    if not clean_keywords and not intervals:
        diagnostics.append(
            RuleDiagnostic("error", "empty_classification", "请添加关键词或数值区间")
        )
    if intervals and not value_column:
        diagnostics.append(RuleDiagnostic("error", "value_column", "数值区间需要选择数据列"))
    data: dict[str, Any] = dict((("version", "1.0"), ("description", "向导生成的分类规则")))
    extract: list[dict[str, Any]] = []
    if clean_keywords:
        extract.append(
            {
                "name": "scene",
                "function": "extract_from_path",
                "params": {"patterns": clean_keywords},
            }
        )
    if intervals:
        extract.append(
            {
                "name": "value",
                "function": "calculate_median",
                "params": {"column": value_column, "samples": 50},
            }
        )
    if extract:
        data["extract"] = extract
    classifications: list[dict[str, str]] = []
    for label, minimum, maximum in intervals:
        condition = _interval_condition(minimum, maximum)
        prefix = "{scene}/" if clean_keywords else ""
        classifications.append({"target": f"{prefix}{label}", "condition": condition})
    if not intervals and clean_keywords:
        classifications.append({"target": "{scene}", "condition": "scene != ''"})
    if classifications:
        data["classify"] = classifications
    data["default"] = "unclassified"
    return RuleDraft("classify", name, _dump_yaml(data), diagnostics)


def build_evaluate_rule(
    eval_type: str,
    ref_column: str,
    pred_column: str,
    *,
    sample_rate: int = 25,
    methods: Sequence[str] = ("mae", "rmse", "correlation"),
    diff_threshold: float | None = None,
    stale_minutes: float | None = None,
    scene_keywords: Mapping[str, Sequence[str]] | None = None,
    name: str = "generated_evaluate.yaml",
) -> RuleDraft:
    diagnostics: list[RuleDiagnostic] = []
    if not ref_column or not pred_column:
        diagnostics.append(RuleDiagnostic("error", "columns", "请选择参考列和算法输出列"))
    data: dict[str, Any] = dict(
        (
            ("description", "向导生成的评估规则"),
            ("type", eval_type),
            ("ref_column", ref_column),
            ("pred_column", pred_column),
        )
    )
    anomaly: dict[str, Any] = {"sample_rate": sample_rate}
    if diff_threshold is not None:
        anomaly["diff_threshold"] = diff_threshold
    if stale_minutes is not None:
        anomaly["stale_minutes"] = stale_minutes
    data["anomaly"] = anomaly
    if scene_keywords:
        data["classify"] = {"by_directory": scene_keywords, "by_filename": scene_keywords}
    data["methods"] = list(methods)
    data["first_output_time"] = True
    data["default_category"] = "other"
    return RuleDraft("evaluate", name, _dump_yaml(data), diagnostics)


def _role_config(groups: Sequence[ChipColumnGroup], expanded: list[str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    frame = next(
        (column for group in groups if group.role == "frame" for column in group.columns), None
    )
    if frame:
        config["frame_column"] = frame
    acc = [column for group in groups if group.role == "acc" for column in group.columns]
    if acc:
        config["acc_columns"] = dict(
            (axis, column) for axis, column in zip(("x", "y", "z"), acc, strict=False)
        )
    factory = [
        group.compact or column
        for group in groups
        if group.role == "factory"
        for column in (group.columns[:1] if group.compact else group.columns)
    ]
    if factory:
        config["factory_columns"] = factory
    check_columns: dict[str, list[str]] = {}
    for role in ("factory", "ipd", "agc"):
        values = [
            group.compact or column
            for group in groups
            if group.role == role
            for column in (group.columns[:1] if group.compact else group.columns)
        ]
        if values:
            check_columns["data" if role == "factory" else role] = values
    if check_columns:
        config["check_columns"] = check_columns
    refs = [column for group in groups if group.role == "reference" for column in group.columns]
    if refs:
        if "REF_RESULT0" in refs:
            config["hr_ref_column"] = {"REF_RESULT0": expanded.index("REF_RESULT0") + 1}
        if "REF_RESULT5" in refs:
            config["spo_ref_column"] = {"REF_RESULT5": expanded.index("REF_RESULT5") + 1}
    return config


def load_chip_columns(chip: str) -> tuple[str, ...]:
    catalog = run_list_rules(RuleListRequest(RuleType.CHIP)).rules
    info = next((item for item in catalog if item.path.stem == chip or item.name == chip), None)
    if info is None:
        return ()
    document = run_read_rule(RuleReadRequest(info.rule_type, info.name, info.source))
    data = YAML(typ="safe").load(document.source) or {}
    values = data.get("columns", [])
    result: list[str] = []
    for value in values if isinstance(values, list) else []:
        result.extend(_expand_column(str(value)))
    return tuple(result)


def _expand_column(value: str) -> list[str]:
    match = re.fullmatch(r"(.*)\{(-?\d+)-(-?\d+)\}(.*)", value)
    if not match:
        return [value]
    prefix, start, end, suffix = match.groups()
    step = 1 if int(end) >= int(start) else -1
    return [f"{prefix}{index}{suffix}" for index in range(int(start), int(end) + step, step)]


def _interval_condition(minimum: float | None, maximum: float | None) -> str:
    if minimum is not None and maximum is not None:
        return f"value >= {minimum:g} and value < {maximum:g}"
    if minimum is not None:
        return f"value >= {minimum:g}"
    if maximum is not None:
        return f"value < {maximum:g}"
    return "True"


def _unique_name(value: str, used: set[str]) -> str:
    base = re.sub(r"\W+", "_", value).strip("_") or "pattern"
    name = base
    index = 2
    while name in used:
        name = f"{base}_{index}"
        index += 1
    return name


def _dump_yaml(data: Any) -> str:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    stream = io.StringIO()
    yaml.dump(data, stream)
    return stream.getvalue()
