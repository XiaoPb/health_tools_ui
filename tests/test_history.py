from __future__ import annotations

import sqlite3
from pathlib import Path

from health_tools_ui.history import HistoryStore
from health_tools_ui.models import JobRecord, JobRequest, JobStatus


def test_history_round_trip(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    request = JobRequest("info", ["info", "数据.csv"], {"target": "数据.csv"})
    record = JobRecord(request, status=JobStatus.SUCCEEDED, exit_code=0, log="ok")
    store.save(record)
    restored = store.recent()
    assert len(restored) == 1
    assert restored[0].request.argv == ["info", "数据.csv"]
    assert restored[0].status == JobStatus.SUCCEEDED


def test_history_updates_existing_job(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.sqlite3")
    record = JobRecord(JobRequest("validate", ["validate", "a.yaml"], {}))
    store.save(record)
    record.status = JobStatus.FAILED
    record.exit_code = 1
    record.request.output_path = "generated/report.csv"
    store.save(record)
    restored = store.recent()[0]
    assert restored.status == JobStatus.FAILED
    assert restored.exit_code == 1
    assert restored.request.output_path == "generated/report.csv"


def test_history_migrates_legacy_database(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, command TEXT NOT NULL, argv_json TEXT NOT NULL,
                values_json TEXT NOT NULL, output_path TEXT, status TEXT NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                exit_code INTEGER, log TEXT NOT NULL DEFAULT ''
            )
            """
        )
    store = HistoryStore(path)
    record = JobRecord(JobRequest("info", [], {"target": "a.csv"}))
    record.result = {"kind": "InfoResult"}
    store.save(record)
    assert store.recent()[0].result == {"kind": "InfoResult"}
