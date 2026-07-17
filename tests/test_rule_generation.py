from __future__ import annotations

from pathlib import Path

from health_tools.api import ValidateRequest, run_validate
from ruamel.yaml import YAML

from health_tools_ui.rule_generation import (
    COMMON_CHIP_TEMPLATES,
    ChipColumnGroup,
    analyze_log,
    build_chip_rule,
    build_classify_rule,
    build_evaluate_rule,
    build_parse_rule,
    initialize_convert_mapping,
    profile_csv,
    render_convert_rule,
)


def test_real_log_finds_four_main_groups() -> None:
    path = Path("E:/Code/Python/health_tools/test_data/log_0512171602.log")
    if not path.exists():
        return
    candidates = analyze_log(path)
    by_marker = {
        item.marker: item for item in candidates if item.marker in {"HR", "HRV", "ADT", "ADTdata"}
    }

    assert set(by_marker) == {"HR", "HRV", "ADT", "ADTdata"}
    assert by_marker["HR"].field_count == 19
    assert by_marker["HR"].count > 8_000
    assert by_marker["HRV"].grammar == "key_value"
    assert by_marker["ADT"].columns == ("wear_status", "det_status", "ctr")
    assert by_marker["ADTdata"].field_count == 15


def test_log_analyzer_excludes_truncated_rows_as_anomalies(tmp_path: Path) -> None:
    path = tmp_path / "sample.log"
    path.write_text(
        "[T] [Comp] [HR],1,2,3\n"
        "[T] [Comp] [HR],4,5,6\n"
        "[T] [Comp] [HR],7,8,9\n"
        "[T] [Comp] [HR],10,[T] interrupted\n",
        encoding="utf-8-sig",
    )

    candidate = analyze_log(path)[0]

    assert candidate.count == 3
    assert candidate.anomaly_count == 1


def test_csv_profile_detects_bom_delimiter_header_and_types(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("Version 1\nTime;ACCX;Label\n1;2.5;sit\n2;3.0;stand\n", encoding="utf-8-sig")

    profile = profile_csv(path)

    assert profile.encoding == "utf-8-sig"
    assert profile.delimiter == ";"
    assert profile.info_row == 1
    assert profile.header_row == 2
    assert profile.columns == ("Time", "ACCX", "Label")
    assert profile.column_types == ("integer", "number", "text")


def test_parse_builder_creates_multi_pattern_rule() -> None:
    path = Path("E:/Code/Python/health_tools/test_data/log_0512171602.log")
    if not path.exists():
        return
    selected = [
        item for item in analyze_log(path) if item.marker in {"HR", "HRV", "ADT", "ADTdata"}
    ]

    draft = build_parse_rule(selected)
    data = YAML(typ="safe").load(draft.source)

    assert set(data["patterns"]) == {"hr", "hrv", "adt", "adtdata"}
    assert data["patterns"]["hr"]["separator"] == ","
    assert "rri0" in data["patterns"]["hrv"]["columns"]


def test_chip_builder_supports_sample_and_extra_template_columns(tmp_path: Path) -> None:
    path = tmp_path / "chip.csv"
    path.write_text("TimeStamp,FRAME_ID,ACCX,ACCY,ACCZ\n1,2,3,4,5\n", encoding="utf-8")
    profile = profile_csv(path)
    groups = (
        ChipColumnGroup("样本", profile.columns),
        next(item for item in COMMON_CHIP_TEMPLATES if item.name == "算法输出"),
        next(item for item in COMMON_CHIP_TEMPLATES if item.name == "参考值"),
    )

    draft = build_chip_rule(profile, "demo", groups)
    data = YAML(typ="safe").load(draft.source)

    assert data["columns"][-2:] == ["ALGO_RESULT{0-15}", "REF_RESULT{0-15}"]
    assert data["hr_ref_column"]["REF_RESULT0"] > 5
    assert draft.has_warnings


def test_convert_initial_mapping_and_warning_for_zero_filled_targets(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("TimeStamp,FRAME_ID,ACCX\n1,2,3\n", encoding="utf-8")
    profile = profile_csv(path)

    mappings = initialize_convert_mapping(path, "gh3220")
    draft = render_convert_rule(profile, "gh3220", mappings)

    assert {item.source for item in mappings} == set(profile.columns)
    assert "missingTargets" in draft.metadata
    assert any(item.code == "zero_filled_targets" for item in draft.diagnostics)


def test_classify_and_evaluate_builders_create_guided_structures() -> None:
    classify = build_classify_rule(
        {"sit": ["静坐", "sitting"], "supine": ["平躺"]},
        (("normal", 95, None), ("low", 90, 95)),
        value_column="REF_RESULT5",
    )
    evaluate = build_evaluate_rule(
        "spo2",
        "REF_RESULT5",
        "ALGO_RESULT0",
        scene_keywords={"sit": ["静坐"]},
    )

    classify_data = YAML(typ="safe").load(classify.source)
    evaluate_data = YAML(typ="safe").load(evaluate.source)
    assert classify_data["extract"][0]["function"] == "extract_from_path"
    assert classify_data["classify"][0]["target"] == "{scene}/normal"
    assert evaluate_data["type"] == "spo2"
    assert evaluate_data["classify"]["by_directory"]["sit"] == ["静坐"]


def test_generated_parse_and_classify_pass_public_validation(tmp_path: Path) -> None:
    log = tmp_path / "sample.log"
    log.write_text(
        "[T] [Comp] [HR],1,2,3\n[T] [Comp] [HR],4,5,6\n[T] [Comp] [HR],7,8,9\n",
        encoding="utf-8",
    )
    parse = build_parse_rule(analyze_log(log))
    classify = build_classify_rule({"sit": ["静坐"], "stand": ["站立"]})

    parse_path = tmp_path / "parse" / "generated.yaml"
    classify_path = tmp_path / "classify" / "generated.yaml"
    parse_path.parent.mkdir()
    classify_path.parent.mkdir()
    parse_path.write_text(parse.source, encoding="utf-8")
    classify_path.write_text(classify.source, encoding="utf-8")

    assert run_validate(ValidateRequest(parse_path)).valid
    assert run_validate(ValidateRequest(classify_path)).valid
