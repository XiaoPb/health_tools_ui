from __future__ import annotations

from pathlib import Path

from health_tools.api import (
    AnalyzeRequest,
    AnalyzeResult,
    BatchResult,
    CheckResult,
    ConfigAction,
    ConfigResult,
    InfoResult,
    ItemResult,
    ItemStatus,
    OfflineResult,
    ValidationResult,
)

from health_tools_ui.api_adapter import (
    build_request,
    result_artifacts,
    result_has_failures,
    serialize_result,
)


def test_builds_analyze_request_with_paths_and_focus_patterns(tmp_path: Path) -> None:
    request = build_request(
        "analyze",
        {
            "input_path": str(tmp_path / "input"),
            "output_path": str(tmp_path / "output"),
            "analysis_type": "spo2",
            "focus": ["static/*", "low-pi/*"],
        },
    )

    assert isinstance(request, AnalyzeRequest)
    assert request.input_path == tmp_path / "input"
    assert request.output_path == tmp_path / "output"
    assert request.analysis_type == "spo2"
    assert request.focus == ("static/*", "low-pi/*")


def test_serializes_every_public_result_shape() -> None:
    batch = BatchResult(
        "parse",
        (ItemResult(ItemStatus.FAIL, "bad.csv", reason="invalid"),),
        (Path("out.csv"),),
    )
    results = (
        batch,
        InfoResult(Path("in.csv"), "csv", {"rows": 1}),
        ValidationResult(Path("rule.yaml"), True),
        ConfigResult(ConfigAction.SHOW, {"rules_dir": "rules"}),
        CheckResult(batch, Path("report.csv")),
        OfflineResult(batch, Path("output")),
        AnalyzeResult(batch, Path("analysis")),
    )
    payloads = [serialize_result(result) for result in results]
    assert [payload["kind"] for payload in payloads] == [
        "BatchResult",
        "InfoResult",
        "ValidationResult",
        "ConfigResult",
        "CheckResult",
        "OfflineResult",
        "AnalyzeResult",
    ]
    assert payloads[-1]["counts"]["fail"] == 1
    assert result_has_failures(payloads[0]) is True
    assert result_artifacts(payloads[0]) == ["out.csv"]
