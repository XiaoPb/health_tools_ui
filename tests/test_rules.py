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
    document.set_value("/column_mapping/red", "rawdata1")
    source = document.source()
    assert "# retained comment" in source
    assert "unknown_extension" in source
    assert "red: rawdata1" in source


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
