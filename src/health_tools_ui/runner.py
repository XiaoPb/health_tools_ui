from __future__ import annotations

import json
import os
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any

import psutil
from health_tools.api import ExecutionContext, GHealthError, OperationCancelled
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QThread, QTimer, Signal, Slot

from .api_adapter import (
    build_request,
    operation_runner,
    result_has_failures,
    result_output,
    serialize_result,
    to_jsonable,
)
from .history import HistoryStore
from .models import JobRecord, JobRequest, JobStatus


def worker_command(_values: dict[str, Any] | list[str] | None = None) -> tuple[str, list[str]]:
    if getattr(sys, "frozen", False):
        return sys.executable, ["--offline-worker"]
    return sys.executable, ["-m", "health_tools_ui", "--offline-worker"]


class ApiWorker(QObject):
    progress = Signal(dict)
    succeeded = Signal(dict)
    cancelled = Signal(dict, str)
    failed = Signal(str, str)

    def __init__(self, command: str, values: dict[str, Any], cancel_event: Event) -> None:
        super().__init__()
        self.command = command
        self.values = values
        self.cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        try:
            request = build_request(self.command, self.values)
            result = operation_runner(self.command)(
                request,
                context=ExecutionContext(
                    on_progress=lambda event: self.progress.emit(to_jsonable(event)),
                    is_cancelled=self.cancel_event.is_set,
                ),
            )
            self.succeeded.emit(serialize_result(result))
        except OperationCancelled as exc:
            result = serialize_result(exc.partial_result) if exc.partial_result is not None else {}
            self.cancelled.emit(result, exc.stage)
        except GHealthError as exc:
            self.failed.emit(type(exc).__name__, str(exc))
        except Exception as exc:
            self.failed.emit(type(exc).__name__, str(exc))


class JobQueue(QObject):
    changed = Signal()
    logChanged = Signal(str)
    jobFinished = Signal(str, str)

    def __init__(self, history: HistoryStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.history = history
        self.records: list[JobRecord] = history.recent()
        self._pending: deque[JobRecord] = deque()
        self._current: JobRecord | None = None
        self._thread: QThread | None = None
        self._worker: ApiWorker | None = None
        self._process: QProcess | None = None
        self._cancel_event: Event | None = None
        self._stdout_buffer = ""
        self._finishing = False

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
        return self.enqueue(
            JobRequest(
                source.request.command, [], dict(source.request.values), source.request.output_path
            )
        )

    def cancel_current(self) -> bool:
        if self._current is None:
            return False
        self._append_log("\n[Health Tools UI] Cancellation requested.\n")
        if self._cancel_event is not None:
            self._cancel_event.set()
        elif self._process is not None:
            self._process.write(b'{"type":"cancel"}\n')
            pid = int(self._process.processId())
            QTimer.singleShot(8000, lambda: self._kill_tree(pid))
        else:
            return False
        self.changed.emit()
        return True

    def _kill_tree(self, pid: int) -> None:
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            return
        try:
            process = psutil.Process(pid)
            for child in reversed(process.children(recursive=True)):
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
        self._finishing = False
        self.changed.emit()
        if self._current.request.command == "offline":
            self._start_offline()
        else:
            self._start_thread()

    def _start_thread(self) -> None:
        assert self._current is not None
        self._cancel_event = Event()
        thread = QThread(self)
        worker = ApiWorker(
            self._current.request.command, dict(self._current.request.values), self._cancel_event
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._thread_succeeded)
        worker.cancelled.connect(self._thread_cancelled)
        worker.failed.connect(self._finish_error)
        thread.finished.connect(self._thread_stopped)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _start_offline(self) -> None:
        assert self._current is not None
        program, arguments = worker_command()
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUTF8", "1")
        environment.insert("PYTHONUNBUFFERED", "1")
        source_root = str(Path(__file__).resolve().parents[1])
        environment.insert(
            "PYTHONPATH",
            os.pathsep.join(filter(None, [source_root, environment.value("PYTHONPATH")])),
        )
        process.setProcessEnvironment(environment)
        process.started.connect(self._send_offline_request)
        process.readyReadStandardOutput.connect(self._read_offline_output)
        process.readyReadStandardError.connect(self._read_offline_error)
        process.finished.connect(self._offline_finished)
        process.errorOccurred.connect(lambda error: self._finish_error("ProcessError", error.name))
        self._process = process
        self._stdout_buffer = ""
        process.start(program, arguments)

    def _send_offline_request(self) -> None:
        if self._process is None or self._current is None:
            return
        payload = (
            json.dumps({"type": "run", "values": self._current.request.values}, ensure_ascii=False)
            + "\n"
        )
        self._process.write(payload.encode("utf-8"))

    def _read_offline_output(self) -> None:
        if self._process is None:
            return
        self._stdout_buffer += bytes(self._process.readAllStandardOutput().data()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._append_log(f"\n[Protocol] {line}\n")
                continue
            kind = message.get("type")
            if kind == "progress":
                self._on_progress(message.get("event", {}))
            elif kind == "result":
                self._finish_result(message.get("result", {}), JobStatus.SUCCEEDED)
            elif kind == "cancelled":
                self._finish_result(
                    message.get("result") or {},
                    JobStatus.CANCELLED,
                    message=str(message.get("stage", "")),
                )
            elif kind == "error":
                self._finish_error(
                    str(message.get("error_type", "OperationError")),
                    str(message.get("message", "")),
                )

    def _read_offline_error(self) -> None:
        if self._process is None:
            return
        text = bytes(self._process.readAllStandardError().data()).decode("utf-8", errors="replace")
        if text:
            self._append_log(text)

    @Slot(dict)
    def _on_progress(self, event: dict[str, Any]) -> None:
        if self._current is None:
            return
        self._current.stage = str(event.get("stage", ""))
        self._current.completed = int(event.get("completed", 0))
        total = event.get("total")
        self._current.total = int(total) if total is not None else None
        self._current.message = str(event.get("message", ""))
        current = event.get("current_item") or ""
        total_text = "?" if self._current.total is None else str(self._current.total)
        self._append_log(
            f"[{self._current.stage}] {self._current.completed}/{total_text} "
            f"{self._current.message} {current}\n"
        )

    @Slot(dict)
    def _thread_succeeded(self, result: dict[str, Any]) -> None:
        self._finish_result(result, JobStatus.SUCCEEDED)

    @Slot(dict, str)
    def _thread_cancelled(self, result: dict[str, Any], stage: str) -> None:
        self._finish_result(result, JobStatus.CANCELLED, message=stage)

    def _finish_result(
        self, result: dict[str, Any], status: JobStatus, *, message: str = ""
    ) -> None:
        if self._finishing or self._current is None:
            return
        if status == JobStatus.SUCCEEDED and result_has_failures(result):
            status = JobStatus.PARTIAL
        self._current.result = result
        if not self._current.request.output_path:
            self._current.request.output_path = result_output(result)
        self._current.status = status
        if message:
            self._current.message = message
        self._finish_common()

    @Slot(str, str)
    def _finish_error(self, error_type: str, message: str) -> None:
        if self._finishing or self._current is None:
            return
        self._current.status = JobStatus.FAILED
        self._current.error_type = error_type
        self._current.error_message = message
        self._append_log(f"\n[{error_type}] {message}\n")
        self._finish_common()

    def _finish_common(self) -> None:
        assert self._current is not None
        self._finishing = True
        self._current.finished_at = datetime.now(UTC).isoformat()
        self.history.save(self._current)
        self.changed.emit()
        self.jobFinished.emit(self._current.request.id, self._current.status.value)
        if self._thread is not None:
            self._thread.quit()

    def _thread_stopped(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None
        self._cancel_event = None
        self._current = None
        self._finishing = False
        self.changed.emit()
        QTimer.singleShot(0, self._start_next)

    def _offline_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._read_offline_output()
        self._read_offline_error()
        if self._current is not None and not self._finishing:
            self._finish_error("WorkerExit", f"Offline worker exited with code {exit_code}")
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self._current = None
        self._finishing = False
        self.changed.emit()
        QTimer.singleShot(0, self._start_next)

    def _append_log(self, chunk: str) -> None:
        if self._current is None:
            return
        self._current.log += chunk
        self.logChanged.emit(self._current.log)
        self.changed.emit()
