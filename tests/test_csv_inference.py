from __future__ import annotations

from pathlib import Path

from health_tools_ui.csv_inference import infer_csv_columns
from health_tools_ui.rules import RuleDocument


def test_infer_columns_uses_first_valid_row_then_second(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    first.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
    result = infer_csv_columns(first)
    assert result is not None
    assert result.columns == ("A", "B", "C")
    assert result.row == 1

    second = tmp_path / "second.csv"
    second.write_text("Version 1\nA,B,C\n", encoding="utf-8")
    result = infer_csv_columns(second)
    assert result is not None
    assert result.columns == ("A", "B", "C")
    assert result.row == 2


def test_infer_columns_skips_when_both_rows_are_invalid(tmp_path: Path) -> None:
    path = tmp_path / "invalid.csv"
    path.write_text("info\nvalue\n", encoding="utf-8")
    assert infer_csv_columns(path) is None


def test_inferred_columns_update_parse_and_convert_rules() -> None:
    parse = RuleDocument.from_source("version: '1.0'\nregex: ''\ncolumns: []\n", kind="parse")
    parse.apply_inferred_columns(["A", "B"])
    assert parse.data["columns"] == ["A", "B"]

    convert = RuleDocument.from_source(
        "version: '1.0'\ncolumn_mapping:\n  A: TARGET_A\n", kind="convert"
    )
    convert.apply_inferred_columns(["A", "B"])
    assert convert.data["column_mapping"] == {"A": "TARGET_A", "B": "B"}
