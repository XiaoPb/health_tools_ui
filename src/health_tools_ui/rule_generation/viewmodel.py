from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any

from health_tools.api import (
    ExecutionContext,
    GHealthError,
    OperationCancelled,
    RuleSaveRequest,
    RuleType,
    run_save_rule,
)
from PySide6.QtCore import Property, QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from .analysis import analyze_log, profile_csv
from .builders import (
    COMMON_CHIP_TEMPLATES,
    build_chip_rule,
    build_classify_rule,
    build_evaluate_rule,
    build_parse_rule,
    initialize_convert_mapping,
    load_chip_columns,
    render_convert_rule,
)
from .models import ChipColumnGroup, ColumnMappingDraft, CsvProfile, LogGroupCandidate, RuleDraft
from .preview import RulePreviewSession

RULE_GENERATOR_KINDS = ("parse", "convert", "chip", "classify", "evaluate")


class _AnalysisWorker(QObject):
    succeeded = Signal(str, object)
    progress = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, kind: str, path: Path, cancelled: Event) -> None:
        super().__init__()
        self.kind = kind
        self.path = path
        self.cancelled = cancelled

    @Slot()
    def run(self) -> None:
        try:
            if self.cancelled.is_set():
                return
            result = (
                analyze_log(
                    self.path,
                    on_progress=self.progress.emit,
                    is_cancelled=self.cancelled.is_set,
                )
                if self.kind == "parse"
                else profile_csv(self.path)
            )
            if not self.cancelled.is_set():
                self.succeeded.emit(self.kind, result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class _PreviewWorker(QObject):
    progress = Signal(dict)
    succeeded = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        session: RulePreviewSession,
        draft: RuleDraft,
        input_path: Path,
        cancelled: Event,
    ) -> None:
        super().__init__()
        self.session = session
        self.draft = draft
        self.input_path = input_path
        self.cancelled_event = cancelled

    @Slot()
    def run(self) -> None:
        try:
            result = self.session.run(
                self.draft,
                self.input_path,
                context=ExecutionContext(
                    on_progress=lambda event: self.progress.emit(
                        {
                            "stage": event.stage,
                            "completed": event.completed,
                            "total": event.total if event.total is not None else -1,
                            "message": event.message,
                        }
                    ),
                    is_cancelled=self.cancelled_event.is_set,
                ),
            )
            self.succeeded.emit(f"预览完成：{len(result.artifacts)} 个输出")
        except OperationCancelled as exc:
            self.cancelled.emit(exc.stage)
        except GHealthError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class RuleGeneratorViewModel(QObject):
    changed = Signal()
    statusChanged = Signal()
    warningConfirmationRequested = Signal()
    draftSaved = Signal(str)

    def __init__(self, parent: QObject | None = None, rule_catalog: Any = None) -> None:
        super().__init__(parent)
        self.rule_catalog = rule_catalog
        self._kind = "parse"
        self._sample_path = ""
        self._profile: CsvProfile | None = None
        self._log_candidates: tuple[LogGroupCandidate, ...] = ()
        self._selected_log_groups: set[str] = set()
        self._target_chip = ""
        self._mappings: list[ColumnMappingDraft] = []
        self._chip_groups: list[ChipColumnGroup] = []
        self._keywords: list[dict[str, Any]] = []
        self._intervals: list[dict[str, Any]] = []
        self._eval_type = "hr"
        self._ref_column = ""
        self._pred_column = ""
        self._sample_rate = 25
        self._eval_methods = ["mae", "rmse", "correlation"]
        self._diff_threshold = 10.0
        self._stale_minutes = 2.0
        self._draft = RuleDraft("parse", "generated_parse.yaml", "")
        self._status = "请选择 LOG 文件"
        self._busy = False
        self._progress: dict[str, Any] = {
            "stage": "",
            "completed": 0,
            "total": -1,
            "message": "",
        }
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._cancelled: Event | None = None
        self._preview_session: RulePreviewSession | None = None

    @Property(str, notify=changed)
    def kind(self) -> str:
        return self._kind

    @Property(list, constant=True)
    def kinds(self) -> list[dict[str, str]]:
        labels = {
            "parse": "日志解析",
            "convert": "格式转换",
            "chip": "芯片格式",
            "classify": "数据分类",
            "evaluate": "指标评估",
        }
        return [{"label": labels[kind], "value": kind} for kind in RULE_GENERATOR_KINDS]

    @Property(str, notify=changed)
    def samplePath(self) -> str:
        return self._sample_path

    @Property(dict, notify=changed)
    def csvProfile(self) -> dict[str, Any]:
        return self._profile.to_dict() if self._profile is not None else {}

    @Property(list, notify=changed)
    def columns(self) -> list[dict[str, str]]:
        return [
            {"key": column, "value": column, "label": column}
            for column in (self._profile.columns if self._profile else ())
        ]

    @Property(list, notify=changed)
    def logCandidates(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._log_candidates]

    @Property(list, notify=changed)
    def selectedLogGroups(self) -> list[str]:
        return sorted(self._selected_log_groups)

    @Property(list, notify=changed)
    def chipChoices(self) -> list[dict[str, Any]]:
        if self.rule_catalog is None:
            return []
        return self.rule_catalog.choices("chip")

    @Property(str, notify=changed)
    def targetChip(self) -> str:
        return self._target_chip

    @Property(list, notify=changed)
    def targetColumns(self) -> list[dict[str, str]]:
        return [
            {"key": column, "value": column, "label": column}
            for column in load_chip_columns(self._target_chip)
        ]

    @Property(list, notify=changed)
    def mappings(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._mappings]

    @Property(list, notify=changed)
    def chipGroups(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._chip_groups]

    @Property(list, constant=True)
    def chipTemplates(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in COMMON_CHIP_TEMPLATES]

    @Property(list, notify=changed)
    def keywordRows(self) -> list[dict[str, Any]]:
        return list(self._keywords)

    @Property(list, notify=changed)
    def intervalRows(self) -> list[dict[str, Any]]:
        return list(self._intervals)

    @Property(str, notify=changed)
    def evalType(self) -> str:
        return self._eval_type

    @Property(str, notify=changed)
    def refColumn(self) -> str:
        return self._ref_column

    @Property(str, notify=changed)
    def predColumn(self) -> str:
        return self._pred_column

    @Property(int, notify=changed)
    def sampleRate(self) -> int:
        return self._sample_rate

    @Property(list, constant=True)
    def evalMethodChoices(self) -> list[dict[str, str]]:
        values = ("mae", "rmse", "std", "correlation", "within_3", "within_5", "within_10")
        return [{"key": value, "value": value, "label": value} for value in values]

    @Property(list, notify=changed)
    def selectedEvalMethods(self) -> list[str]:
        return list(self._eval_methods)

    @Property(float, notify=changed)
    def diffThreshold(self) -> float:
        return self._diff_threshold

    @Property(float, notify=changed)
    def staleMinutes(self) -> float:
        return self._stale_minutes

    @Property(str, notify=changed)
    def draftSource(self) -> str:
        return self._draft.source

    @Property(str, notify=changed)
    def draftName(self) -> str:
        return self._draft.name

    @Property(list, notify=changed)
    def diagnostics(self) -> list[dict[str, str]]:
        return [item.to_dict() for item in self._draft.diagnostics]

    @Property(bool, notify=changed)
    def busy(self) -> bool:
        return self._busy

    @Property(dict, notify=changed)
    def progress(self) -> dict[str, Any]:
        return dict(self._progress)

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Slot(str)
    def setKind(self, kind: str) -> None:
        if kind not in RULE_GENERATOR_KINDS or kind == self._kind:
            return
        self.cancel()
        self._kind = kind
        self._sample_path = ""
        self._profile = None
        self._log_candidates = ()
        self._selected_log_groups.clear()
        self._mappings.clear()
        self._chip_groups.clear()
        self._draft = RuleDraft(kind, f"generated_{kind}.yaml", "")
        self._set_status("请选择样本文件")
        self.changed.emit()

    @Slot()
    def chooseSample(self) -> None:
        file_filter = (
            "LOG (*.log *.txt);;所有文件 (*)"
            if self._kind == "parse"
            else "CSV (*.csv *.txt);;所有文件 (*)"
        )
        path, _ = QFileDialog.getOpenFileName(None, "选择样本", filter=file_filter)
        if path:
            self.loadSample(path)

    @Slot(str)
    def loadSample(self, path: str) -> None:
        target = Path(path)
        if not target.is_file():
            self._set_status(f"样本文件不存在：{path}")
            return
        if self._thread is not None and self._thread.isRunning():
            self.cancel()
            self._set_status("正在取消当前分析，请稍后重新选择样本")
            return
        self._sample_path = str(target.resolve())
        self._busy = True
        self._progress = {"stage": "analysis", "completed": 0, "total": -1, "message": "分析样本"}
        cancelled = Event()
        thread = QThread(self)
        worker = _AnalysisWorker(self._kind, target, cancelled)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._analysis_succeeded)
        worker.progress.connect(self._analysis_progress)
        worker.failed.connect(self._analysis_failed)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.destroyed.connect(self._thread_destroyed)
        self._thread = thread
        self._worker = worker
        self._cancelled = cancelled
        self.changed.emit()
        thread.start()

    @Slot(int)
    def _analysis_progress(self, completed: int) -> None:
        self._progress = {
            "stage": "analysis",
            "completed": completed,
            "total": -1,
            "message": f"已扫描 {completed} 行",
        }
        self.changed.emit()

    @Slot(str, object)
    def _analysis_succeeded(self, kind: str, result: Any) -> None:
        if kind == "parse":
            all_candidates = tuple(result)
            preferred = [
                item for item in all_candidates if item.count >= 50 and item.field_count >= 2
            ]
            self._log_candidates = tuple(preferred or all_candidates)
            self._selected_log_groups = {item.key for item in self._log_candidates[:12]}
            self._set_status(f"识别到 {len(self._log_candidates)} 个结构化日志分组")
        else:
            self._profile = result
            self._chip_groups = [
                ChipColumnGroup(column, (column,), _infer_role(column))
                for column in self._profile.columns
            ]
            if self._profile.columns:
                self._ref_column = self._profile.columns[0]
                self._pred_column = self._profile.columns[min(1, len(self._profile.columns) - 1)]
            self._set_status(f"读取到 {len(self._profile.columns)} 列")
        self.changed.emit()

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        self._set_status(message)

    @Slot()
    def _thread_destroyed(self) -> None:
        self._busy = False
        self._thread = None
        self._worker = None
        self._cancelled = None
        self.changed.emit()

    @Slot(list)
    def setSelectedLogGroups(self, keys: list[Any]) -> None:
        self._selected_log_groups = {str(key) for key in keys}
        self.changed.emit()

    @Slot(str, str)
    def updateLogColumns(self, key: str, columns: str) -> None:
        values = tuple(
            value.strip() for value in columns.replace("，", ",").split(",") if value.strip()
        )
        if not values:
            return
        for index, candidate in enumerate(self._log_candidates):
            if candidate.key == key and len(values) == candidate.field_count:
                self._log_candidates = (
                    *self._log_candidates[:index],
                    replace(candidate, columns=values),
                    *self._log_candidates[index + 1 :],
                )
                self.changed.emit()
                return
        self._set_status("列名数量必须与字段数一致")

    @Slot(str)
    def setTargetChip(self, chip: str) -> None:
        self._target_chip = chip
        if self._profile is not None and chip:
            try:
                self._mappings = list(initialize_convert_mapping(self._profile.path, chip))
                self._set_status(f"已生成 {len(self._mappings)} 条初始映射")
            except Exception as exc:
                self._set_status(str(exc))
        self.changed.emit()

    @Slot(int, str, bool)
    def updateMapping(self, index: int, target: str, enabled: bool) -> None:
        if not 0 <= index < len(self._mappings):
            return
        current = self._mappings[index]
        self._mappings[index] = ColumnMappingDraft(
            current.source, target, enabled, bool(target and target != "Unknown")
        )
        self.changed.emit()

    @Slot(str)
    def addChipTemplate(self, name: str) -> None:
        template = next((item for item in COMMON_CHIP_TEMPLATES if item.name == name), None)
        if template is not None and all(item.name != name for item in self._chip_groups):
            self._chip_groups.append(template)
            self.changed.emit()

    @Slot(str, str)
    def addCustomColumn(self, name: str, role: str = "data") -> None:
        if name.strip():
            value = name.strip()
            self._chip_groups.append(ChipColumnGroup(value, (value,), role))
            self.changed.emit()

    @Slot(str, str, int, int, str)
    def addColumnRange(self, name: str, prefix: str, start: int, end: int, role: str) -> None:
        if not prefix.strip():
            return
        step = 1 if end >= start else -1
        columns = tuple(f"{prefix}{index}" for index in range(start, end + step, step))
        compact = f"{prefix}{{{start}-{end}}}"
        self._chip_groups.append(ChipColumnGroup(name or compact, columns, role, compact))
        self.changed.emit()

    @Slot(int, int)
    def moveChipGroup(self, index: int, offset: int) -> None:
        destination = index + offset
        if 0 <= index < len(self._chip_groups) and 0 <= destination < len(self._chip_groups):
            item = self._chip_groups.pop(index)
            self._chip_groups.insert(destination, item)
            self.changed.emit()

    @Slot(int)
    def removeChipGroup(self, index: int) -> None:
        if 0 <= index < len(self._chip_groups):
            self._chip_groups.pop(index)
            self.changed.emit()

    @Slot(int, str)
    def setChipGroupRole(self, index: int, role: str) -> None:
        if 0 <= index < len(self._chip_groups):
            current = self._chip_groups[index]
            self._chip_groups[index] = ChipColumnGroup(
                current.name, current.columns, role, current.compact
            )
            self.changed.emit()

    @Slot(str, str)
    def addKeyword(self, category: str, words: str) -> None:
        values = [word.strip() for word in words.replace("，", ",").split(",") if word.strip()]
        if category.strip() and values:
            self._keywords.append(
                {
                    "key": f"keyword-{len(self._keywords)}",
                    "category": category.strip(),
                    "words": values,
                }
            )
            self.changed.emit()

    @Slot(int)
    def removeKeyword(self, index: int) -> None:
        if 0 <= index < len(self._keywords):
            self._keywords.pop(index)
            self.changed.emit()

    @Slot(str, float, float)
    def addInterval(self, label: str, minimum: float, maximum: float) -> None:
        if not label.strip() or not math.isfinite(minimum) or not math.isfinite(maximum):
            return
        self._intervals.append(
            {
                "key": f"interval-{len(self._intervals)}",
                "label": label.strip(),
                "minimum": minimum,
                "maximum": maximum,
            }
        )
        self.changed.emit()

    @Slot(int)
    def removeInterval(self, index: int) -> None:
        if 0 <= index < len(self._intervals):
            self._intervals.pop(index)
            self.changed.emit()

    @Slot(str)
    def setClassifyColumn(self, column: str) -> None:
        self._ref_column = column
        self.changed.emit()

    @Slot(str, str, str, int)
    def setEvaluateOptions(
        self, eval_type: str, ref_column: str, pred_column: str, sample_rate: int
    ) -> None:
        self._eval_type = eval_type
        self._ref_column = ref_column
        self._pred_column = pred_column
        self._sample_rate = max(1, sample_rate)
        self.changed.emit()

    @Slot(list)
    def setEvalMethods(self, methods: list[Any]) -> None:
        self._eval_methods = [str(method) for method in methods if str(method)]
        self.changed.emit()

    @Slot(float, float)
    def setEvalThresholds(self, diff_threshold: float, stale_minutes: float) -> None:
        if math.isfinite(diff_threshold):
            self._diff_threshold = diff_threshold
        if math.isfinite(stale_minutes):
            self._stale_minutes = stale_minutes
        self.changed.emit()

    @Slot(str)
    def generate(self, name: str = "") -> None:
        output_name = name.strip() or f"generated_{self._kind}.yaml"
        if not output_name.lower().endswith((".yaml", ".yml")):
            output_name += ".yaml"
        if self._kind == "parse":
            selected = [
                item for item in self._log_candidates if item.key in self._selected_log_groups
            ]
            self._draft = build_parse_rule(selected, name=output_name)
        elif self._kind == "convert" and self._profile is not None:
            self._draft = render_convert_rule(
                self._profile, self._target_chip, self._mappings, name=output_name
            )
        elif self._kind == "chip" and self._profile is not None:
            chip_name = Path(output_name).stem.replace("generated_", "")
            self._draft = build_chip_rule(
                self._profile, chip_name, self._chip_groups, name=output_name
            )
        elif self._kind == "classify":
            keywords = {item["category"]: item["words"] for item in self._keywords}
            intervals = tuple(
                (item["label"], item["minimum"], item["maximum"]) for item in self._intervals
            )
            value_column = self._ref_column or (self._profile.columns[0] if self._profile else "")
            self._draft = build_classify_rule(
                keywords, intervals, value_column=value_column, name=output_name
            )
        elif self._kind == "evaluate":
            self._draft = build_evaluate_rule(
                self._eval_type,
                self._ref_column,
                self._pred_column,
                sample_rate=self._sample_rate,
                methods=self._eval_methods,
                diff_threshold=self._diff_threshold,
                stale_minutes=self._stale_minutes,
                scene_keywords={item["category"]: item["words"] for item in self._keywords},
                name=output_name,
            )
        else:
            self._draft = RuleDraft(
                self._kind,
                output_name,
                "{}\n",
                [],
            )
        self._set_status("规则草稿已生成")
        self.changed.emit()

    @Slot()
    def preview(self) -> None:
        if self._draft.has_errors or not self._draft.source or not self._sample_path:
            self._set_status("请先生成无硬错误的规则草稿")
            return
        if self._kind == "chip":
            self._set_status("Chip 规则通过样本列差异预览，无需执行任务")
            return
        self.cancel()
        if self._preview_session is not None:
            self._preview_session.cleanup()
        self._preview_session = RulePreviewSession()
        cancelled = Event()
        thread = QThread(self)
        worker = _PreviewWorker(
            self._preview_session, self._draft, Path(self._sample_path), cancelled
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._preview_progress)
        worker.succeeded.connect(self._preview_done)
        worker.cancelled.connect(self._preview_cancelled)
        worker.failed.connect(self._analysis_failed)
        worker.succeeded.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.destroyed.connect(self._thread_destroyed)
        self._thread = thread
        self._worker = worker
        self._cancelled = cancelled
        self._busy = True
        self.changed.emit()
        thread.start()

    @Slot(dict)
    def _preview_progress(self, progress: dict[str, Any]) -> None:
        self._progress = progress
        self.changed.emit()

    @Slot(str)
    def _preview_done(self, message: str) -> None:
        self._set_status(message)

    @Slot(str)
    def _preview_cancelled(self, stage: str) -> None:
        self._set_status(f"预览已取消：{stage}")

    @Slot()
    def cancel(self) -> None:
        if self._cancelled is not None:
            self._cancelled.set()

    @Slot(bool)
    def saveDraft(self, confirmed: bool = False) -> None:
        if not self._draft.source.strip():
            self._set_status("请先生成规则草稿")
            return
        if self._draft.has_errors:
            self._set_status("请先解决硬错误")
            return
        if self._draft.has_warnings and not confirmed:
            self.warningConfirmationRequested.emit()
            return
        try:
            existing = (
                self.rule_catalog.asset(self._draft.kind, self._draft.name)
                if self.rule_catalog is not None
                else None
            )
            saved = run_save_rule(
                RuleSaveRequest(
                    RuleType(self._draft.kind),
                    self._draft.name,
                    self._draft.source,
                    expected_revision=existing.revision if existing else None,
                )
            )
            if self.rule_catalog is not None:
                self.rule_catalog.refresh()
            self._set_status(f"已保存 {saved.rule.path}")
            self.draftSaved.emit(str(saved.rule.path))
        except Exception as exc:
            self._set_status(str(exc))

    def cleanup(self) -> None:
        self.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(30_000)
        if self._preview_session is not None:
            self._preview_session.cleanup()
            self._preview_session = None

    def _set_status(self, status: str) -> None:
        self._status = status
        self.statusChanged.emit()


def _infer_role(column: str) -> str:
    lowered = column.lower()
    if "time" in lowered:
        return "time"
    if "frame" in lowered:
        return "frame"
    if lowered in {"accx", "accy", "accz", "acc_x", "acc_y", "acc_z"}:
        return "acc"
    if "algo" in lowered:
        return "algorithm"
    if "ref" in lowered:
        return "reference"
    if "agc" in lowered:
        return "agc"
    if "raw" in lowered or lowered.startswith("ch"):
        return "factory"
    return "data"
