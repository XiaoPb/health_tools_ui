from __future__ import annotations

from pathlib import Path

from health_tools_ui.results import read_result


def test_csv_result_preview(tmp_path: Path) -> None:
    output = tmp_path / "result.csv"
    output.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    result = read_result(str(output))
    assert result["kind"] == "csv"
    assert result["columns"] == ["name", "value"]
    assert result["rows"] == [["alpha", "1"], ["beta", "2"]]


def test_directory_result_lists_files(tmp_path: Path) -> None:
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.log").write_text("two", encoding="utf-8")
    result = read_result(str(tmp_path))
    assert result["kind"] == "files"
    assert result["items"] == ["one.txt", "two.log"]
