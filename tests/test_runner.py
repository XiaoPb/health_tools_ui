from __future__ import annotations

from pathlib import Path

from health_tools_ui.history import HistoryStore
from health_tools_ui.models import JobRequest, JobStatus
from health_tools_ui.runner import JobQueue


def test_queue_runs_worker_and_persists_result(qtbot, tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    queue = JobQueue(store)
    request = JobRequest("help", ["--help"], {})

    with qtbot.waitSignal(queue.jobFinished, timeout=15_000) as signal:
        queue.enqueue(request)

    assert signal.args == [request.id, True]
    record = next(item for item in queue.records if item.request.id == request.id)
    assert record.status == JobStatus.SUCCEEDED
    assert "Commands" in record.log
    assert store.recent()[0].status == JobStatus.SUCCEEDED
