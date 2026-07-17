from __future__ import annotations

from pathlib import Path

from health_tools_ui.rules import RuleDocument

CONVERT_RULE = """# retained comment
version: '1.0'
description: sample
column_mapping:
  red: rawdata0
unknown_extension:
  enabled: true
"""


def test_round_trip_preserves_comments_and_unknown_fields() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")
    assert document.set_value("/column_mapping/red", "rawdata1") is True
    source = document.source()
    assert "# retained comment" in source
    assert "unknown_extension" in source
    assert "red: rawdata1" in source


def test_equal_visual_value_is_not_a_document_change() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")

    assert document.set_value("/column_mapping/red", "rawdata0") is False
    assert document.dirty is False

    assert document.set_value("/column_mapping/red", "rawdata1") is True
    assert document.dirty is True


def test_equal_source_is_not_a_document_change() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")

    assert document.replace_source(document.editor_source()) == []
    assert document.dirty is False


def test_visual_nested_add_and_remove() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")
    document.add_child("/column_mapping", "ir", "rawdata2")
    assert any(entry["pointer"] == "/column_mapping/ir" for entry in document.visual_entries())
    document.remove("/column_mapping/ir")
    assert not any(entry["pointer"] == "/column_mapping/ir" for entry in document.visual_entries())


def test_invalid_source_does_not_replace_document() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")
    issues = document.replace_source("[not: a mapping]")
    assert issues
    assert "column_mapping" in document.data


def test_atomic_save_and_reload(tmp_path: Path) -> None:
    target = tmp_path / "convert" / "rule.yaml"
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")
    document.save(target)
    loaded = RuleDocument.load(target)
    assert loaded.kind == "convert"
    assert loaded.data["column_mapping"]["red"] == "rawdata0"


def test_required_keys_are_validated() -> None:
    document = RuleDocument.from_source("columns: []\n", kind="chip")
    messages = [issue.message_en for issue in document.validate()]
    assert any("version" in message for message in messages)
    assert any("chip" in message for message in messages)


def test_invalid_source_is_retained_for_correction() -> None:
    document = RuleDocument.from_source(CONVERT_RULE, kind="convert")
    invalid = "column_mapping: [\n"
    assert document.replace_source(invalid)
    assert document.editor_source() == invalid
    assert document.data["column_mapping"]["red"] == "rawdata0"
    assert document.validate()[0].message_en == "Invalid YAML syntax"


def test_tree_schema_add_and_list_template() -> None:
    document = RuleDocument.from_source("version: '1.0'\n", kind="convert")
    available = {item["value"] for item in document.available_keys("")}
    assert {"column_mapping", "extra_source"} <= available
    document.add_suggested("", "extra_source")
    document.add_list_item("/extra_source")
    assert document.data["extra_source"][0]["pattern"] == "*.csv"
    tree = document.tree_nodes()
    extra_source = next(node for node in tree if node["key"] == "/extra_source")
    assert extra_source["children"][0]["key"] == "/extra_source/0"


def test_list_items_can_be_reordered() -> None:
    document = RuleDocument.from_source("columns: [one, two]\n", kind="chip")
    document.move_list_item("/columns/1", -1)
    assert document.data["columns"] == ["two", "one"]


def test_patterns_and_multi_pattern_parse_use_supported_local_validation() -> None:
    patterns = RuleDocument.from_source(
        "version: '1.0'\npatterns:\n  sit: [sit]\n", kind="classify"
    )
    assert patterns.variant == "patterns"
    assert patterns.validate() == []

    parse = RuleDocument.from_source(
        "version: '1.0'\npatterns:\n  ppg:\n    regex: '(.*)'\n    columns: [value]\n",
        kind="parse",
    )
    assert parse.validate() == []


def test_analysis_rule_is_detected_and_exposes_nested_schema(tmp_path: Path) -> None:
    source = (
        "version: '1.0'\ntype: hr\ncolumns:\n  reference: REF_RESULT0\n"
        "detectors: [integrity]\nthresholds:\n  error: 10\ncauses:\n"
        "  - id: incomplete\n    title: 数据不完整\n    origin: raw\n"
        "    when: {feature: data_complete, op: eq, value: false}\n"
    )
    document = RuleDocument.from_source(source, tmp_path / "analysis" / "custom.yaml")

    assert document.kind == "analysis"
    assert document.validate() == []
    assert {field["key"] for field in document.form_fields()} >= {
        "columns",
        "detectors",
        "thresholds",
        "causes",
    }
