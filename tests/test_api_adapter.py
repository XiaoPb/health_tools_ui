from __future__ import annotations

from pathlib import Path

from health_tools.api import (
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

from health_tools_ui.api_adapter import result_artifacts, result_has_failures, serialize_result


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
    )
    payloads = [serialize_result(result) for result in results]
    assert [payload["kind"] for payload in payloads] == [
        "BatchResult",
        "InfoResult",
        "ValidationResult",
        "ConfigResult",
        "CheckResult",
        "OfflineResult",
    ]
    assert result_has_failures(payloads[0]) is True
    assert result_artifacts(payloads[0]) == ["out.csv"]
