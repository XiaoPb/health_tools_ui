from __future__ import annotations

import json
import os
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import psutil
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .history import HistoryStore
from .models import JobRecord, JobRequest, JobStatus


def worker_command(argv: list[str]) -> tuple[str, list[str]]:
    payload = json.dumps(argv, ensure_ascii=False)
    if getattr(sys, "frozen", False):
        return sys.executable, ["--worker", payload]
    return sys.executable, ["-m", "health_tools_ui", "--worker", payload]


class JobQueue(QObject):
    changed = Signal()
    logChanged = Signal(str)
    jobFinished = Signal(str, bool)

    def __init__(self, history: HistoryStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.history = history
        self.records: list[JobRecord] = history.recent()
        self._pending: deque[JobRecord] = deque()
        self._current: JobRecord | None = None
        self._process: QProcess | None = None

    @property
    def current(self) -> JobRecord | None:
        return self._current

    def enqueue(self, request: JobRequest) -> JobRecord:
        record = JobRecord(request=request)
        self.records.insert(0, record)
        self._pending.append(record)
        self.history.save(record)
        self.changed.emit()
        self._start_next()
        return record

    def retry(self, job_id: str) -> JobRecord | None:
        source = next((item for item in self.records if item.request.id == job_id), None)
        if source is None:
            return None
        request = JobRequest(
            command=source.request.command,
            argv=list(source.request.argv),
            values=dict(source.request.values),
            output_path=source.request.output_path,
        )
        return self.enqueue(request)

    def cancel_current(self) -> bool:
        if self._current is None or self._process is None:
            return False
        self._current.status = JobStatus.CANCELLED
        self._append_log("\n[Health Tools UI] Cancellation requested.\n")
        self._process.terminate()
        pid = int(self._process.processId())
        QTimer.singleShot(3000, lambda: self._kill_tree(pid))
        self.changed.emit()
        return True

    def _kill_tree(self, pid: int) -> None:
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            return
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)
            for child in reversed(children):
                child.kill()
            process.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._process.kill()

    def _start_next(self) -> None:
        if self._current is not None or not self._pending:
            return
        self._current = self._pending.popleft()
        self._current.status = JobStatus.RUNNING
        self._current.started_at = datetime.now(UTC).isoformat()
        self.history.save(self._current)

        program, arguments = worker_command(self._current.request.argv)
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONUNBUFFERED", "1")
        source_root = str(Path(__file__).resolve().parents[1])
        current_path = environment.value("PYTHONPATH")
        environment.insert("PYTHONPATH", os.pathsep.join(filter(None, [source_root, current_path])))
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        self._process = process
        self.changed.emit()
        process.start(program, arguments)

    def _read_output(self) -> None:
        if self._process is None:
            return
        raw = bytes(self._process.readAllStandardOutput().data())
        chunk = raw.decode("utf-8", errors="replace")
        self._append_log(chunk)

    def _append_log(self, chunk: str) -> None:
        if self._current is None:
            return
        self._current.log += chunk
        self.logChanged.emit(self._current.log)
        self.changed.emit()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if self._current is not None:
            self._append_log(f"\n[Health Tools UI] Process error: {error.name}\n")

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if self._current is None:
            return
        self._read_output()
        record = self._current
        record.exit_code = exit_code
        record.finished_at = datetime.now(UTC).isoformat()
        if record.status != JobStatus.CANCELLED:
            record.status = JobStatus.SUCCEEDED if exit_code == 0 else JobStatus.FAILED
        self.history.save(record)
        self._current = None
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self.changed.emit()
        self.jobFinished.emit(record.request.id, record.status == JobStatus.SUCCEEDED)
        QTimer.singleShot(0, self._start_next)
