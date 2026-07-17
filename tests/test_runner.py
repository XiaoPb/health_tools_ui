from __future__ import annotations

from pathlib import Path

from health_tools.api import BatchResult, ItemResult, ItemStatus

from health_tools_ui.history import HistoryStore
from health_tools_ui.models import JobRequest, JobStatus
from health_tools_ui.runner import JobQueue


def test_queue_runs_api_thread_and_persists_result(qtbot, tmp_path: Path) -> None:
    source = tmp_path / "sample.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    store = HistoryStore(tmp_path / "history.sqlite3")
    queue = JobQueue(store)
    request = JobRequest("info", [], {"target": str(source), "preview": 1})

    with qtbot.waitSignal(queue.jobFinished, timeout=15_000) as signal:
        queue.enqueue(request)

    assert signal.args == [request.id, "succeeded"]
    record = next(item for item in queue.records if item.request.id == request.id)
    assert record.status == JobStatus.SUCCEEDED
    assert record.result["kind"] == "InfoResult"
    assert store.recent()[0].result["kind"] == "InfoResult"


def test_queue_marks_batch_with_failed_items_partial(qtbot, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("health_tools_ui.runner.build_request", lambda _command, values: values)
    monkeypatch.setattr(
        "health_tools_ui.runner.operation_runner",
        lambda _command: (
            lambda _request, context: BatchResult(
                "parse", (ItemResult(ItemStatus.FAIL, "bad.log"),)
            )
        ),
    )
    queue = JobQueue(HistoryStore(tmp_path / "history.sqlite3"))
    request = JobRequest("parse", [], {})
    with qtbot.waitSignal(queue.jobFinished, timeout=5000) as signal:
        queue.enqueue(request)
    assert signal.args == [request.id, "partial"]
    assert queue.records[0].status == JobStatus.PARTIAL
