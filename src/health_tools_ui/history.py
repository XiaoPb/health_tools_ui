from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from platformdirs import user_data_path

from .models import JobRecord, JobRequest, JobStatus


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        data_dir = user_data_path("HealthToolsUI", "XiaoPb")
        self.path = path or data_dir / "history.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    argv_json TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    output_path TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    exit_code INTEGER,
                    log TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def save(self, record: JobRecord) -> None:
        request = record.request
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, command, argv_json, values_json, output_path, status,
                    created_at, started_at, finished_at, exit_code, log
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    started_at=excluded.started_at,
                    finished_at=excluded.finished_at,
                    exit_code=excluded.exit_code,
                    log=excluded.log
                """,
                (
                    request.id,
                    request.command,
                    json.dumps(request.argv, ensure_ascii=False),
                    json.dumps(request.values, ensure_ascii=False),
                    request.output_path,
                    record.status.value,
                    request.created_at,
                    record.started_at,
                    record.finished_at,
                    record.exit_code,
                    record.log,
                ),
            )

    def recent(self, limit: int = 100) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        records: list[JobRecord] = []
        for row in rows:
            request = JobRequest(
                id=row["id"],
                command=row["command"],
                argv=json.loads(row["argv_json"]),
                values=json.loads(row["values_json"]),
                output_path=row["output_path"],
                created_at=row["created_at"],
            )
            records.append(
                JobRecord(
                    request=request,
                    status=JobStatus(row["status"]),
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    exit_code=row["exit_code"],
                    log=row["log"],
                )
            )
        return records
