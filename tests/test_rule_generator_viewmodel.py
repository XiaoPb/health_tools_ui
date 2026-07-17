from __future__ import annotations

from pathlib import Path

from health_tools.api import RuleCatalogResult

from health_tools_ui.resources import RuleCatalogService
from health_tools_ui.rule_generation.viewmodel import RuleGeneratorViewModel


def test_parse_sample_analysis_runs_in_thread_and_generates_draft(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "sample.log"
    path.write_text(
        "[T] [Comp] [HR],1,2,3\n[T] [Comp] [HR],4,5,6\n[T] [Comp] [HR],7,8,9\n",
        encoding="utf-8",
    )
    catalog = RuleCatalogService(list_runner=lambda _request: RuleCatalogResult())
    model = RuleGeneratorViewModel(rule_catalog=catalog)

    model.loadSample(str(path))
    qtbot.waitUntil(lambda: not model.busy, timeout=5_000)
    model.generate("sample.yaml")

    assert len(model.logCandidates) == 1
    assert model.selectedLogGroups == ["Comp:HR:numeric:3"]
    assert "patterns:" in model.draftSource
    assert not any(item["severity"] == "error" for item in model.diagnostics)
    model.cleanup()


def test_chip_sample_starts_with_ordered_columns_and_accepts_templates(
    qtbot, tmp_path: Path
) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("TimeStamp,FRAME_ID,ACCX\n1,2,3\n", encoding="utf-8")
    model = RuleGeneratorViewModel()
    model.setKind("chip")

    model.loadSample(str(path))
    qtbot.waitUntil(lambda: not model.busy, timeout=5_000)
    model.addChipTemplate("算法输出")
    model.addCustomColumn("Temperature", "data")
    model.generate("demo.yaml")

    assert [item["name"] for item in model.chipGroups[:3]] == [
        "TimeStamp",
        "FRAME_ID",
        "ACCX",
    ]
    assert "ALGO_RESULT{0-15}" in model.draftSource
    assert "Temperature" in model.draftSource
    model.cleanup()


def test_repeated_sample_analysis_waits_for_thread_destruction(qtbot, tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text("TimeStamp,FRAME_ID,ACCX\n1,2,3\n", encoding="utf-8")
    model = RuleGeneratorViewModel()
    model.setKind("chip")

    for _ in range(12):
        model.loadSample(str(path))
        qtbot.waitUntil(lambda: not model.busy, timeout=5_000)
        assert model._thread is None

    model.cleanup()
