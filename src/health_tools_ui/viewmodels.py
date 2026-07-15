from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QSettings, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from .arguments import build_argv, is_dangerous, validate_values
from .catalog import build_catalog
from .history import HistoryStore
from .models import CommandSpec, JobRequest
from .results import read_result
from .rules import RULE_KINDS, RuleDocument
from .runner import JobQueue

TEXTS = {
    "zh_CN": {
        "appTitle": "Health Tools UI",
        "run": "运行",
        "cancel": "取消任务",
        "tasks": "任务",
        "rules": "规则中心",
        "settings": "设置",
        "allCommands": "全部命令",
        "basic": "基础参数",
        "advanced": "高级参数",
        "log": "运行日志",
        "visual": "可视化",
        "source": "源码",
        "preview": "预览",
        "validate": "验证",
        "save": "保存",
        "open": "打开",
        "add": "添加",
        "remove": "删除",
        "dangerTitle": "确认高风险操作",
        "dangerBody": "当前参数可能移动、覆盖或分拣文件。确认继续吗？",
        "confirm": "确认运行",
        "noCommand": "请选择一个命令",
        "ready": "就绪",
    },
    "en": {
        "appTitle": "Health Tools UI",
        "run": "Run",
        "cancel": "Cancel job",
        "tasks": "Tasks",
        "rules": "Rule center",
        "settings": "Settings",
        "allCommands": "All commands",
        "basic": "Basic parameters",
        "advanced": "Advanced parameters",
        "log": "Run log",
        "visual": "Visual",
        "source": "Source",
        "preview": "Preview",
        "validate": "Validate",
        "save": "Save",
        "open": "Open",
        "add": "Add",
        "remove": "Remove",
        "dangerTitle": "Confirm risky operation",
        "dangerBody": "These parameters can move, overwrite, or sort files. Continue?",
        "confirm": "Run anyway",
        "noCommand": "Select a command",
        "ready": "Ready",
    },
}

ZH_FIELD_LABELS = {
    "input_path": "输入路径",
    "output_path": "输出路径",
    "rule_file": "规则文件",
    "chip_name": "芯片型号",
    "target": "目标文件",
    "stats": "统计信息",
    "schema": "结构信息",
    "preview": "预览行数",
    "strict": "严格验证",
    "plot_type": "图表类型",
    "channels": "通道",
    "sample_rate": "采样率",
    "window": "窗口大小",
    "overlap": "重叠率",
    "mode": "文件处理方式",
    "filter_name": "文件名过滤",
    "max_workers": "并行线程数",
    "verbose": "详细日志",
    "checks": "检查项目",
    "timeout": "超时时间",
    "rules_dir": "规则目录",
    "offline_path": "离线工具目录",
    "offline_default": "默认离线版本",
    "eval_type": "评估类型",
}


class AppViewModel(QObject):
    currentCommandChanged = Signal()
    valuesChanged = Signal()
    jobsChanged = Signal()
    logChanged = Signal()
    localeChanged = Signal()
    settingsChanged = Signal()
    statusChanged = Signal()
    resultChanged = Signal()
    dangerousConfirmationRequested = Signal()

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._catalog = build_catalog()
        self._by_name = {spec.name: spec for spec in self._catalog}
        self._current: CommandSpec = self._catalog[0]
        self._values: dict[str, Any] = {}
        self._revision = 0
        self._locale = str(settings.value("locale", "zh_CN"))
        self._dark_mode = str(settings.value("darkMode", "false")).lower() == "true"
        self._offline_path = self._discover_offline_path()
        self._status = TEXTS[self._locale]["ready"]
        self._result: dict[str, Any] = {"kind": "none", "title": "", "items": []}
        self._selected_log = ""
        self.queue = JobQueue(HistoryStore(), self)
        self.queue.changed.connect(self.jobsChanged)
        self.queue.logChanged.connect(lambda _log: self.logChanged.emit())
        self.queue.jobFinished.connect(self._job_finished)
        self._reset_values()

    @Property(list, constant=True)
    def commands(self) -> list[dict[str, Any]]:
        return [spec.to_dict() for spec in self._catalog]

    @Property(dict, notify=currentCommandChanged)
    def currentCommand(self) -> dict[str, Any]:
        result = self._current.to_dict()
        if self._locale == "en":
            result["title"] = self._current.name.title()
            result["help"] = f"Configure and run the ghealth-tools {self._current.name} command."
        return result

    @Property(list, notify=currentCommandChanged)
    def currentFields(self) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        for field in self._current.fields:
            item = field.to_dict()
            if item["default"] is None:
                item["default"] = ""
            if self._locale == "zh_CN":
                item["label"] = ZH_FIELD_LABELS.get(field.name, field.label)
            else:
                option = field.flags[0] if field.flags else field.name
                item["help"] = f"ghealth-tools option: {option}"
            fields.append(item)
        return fields

    @Property(int, notify=valuesChanged)
    def valuesRevision(self) -> int:
        return self._revision

    @Property(dict, notify=valuesChanged)
    def valuesForUi(self) -> dict[str, Any]:
        return {name: "" if value is None else value for name, value in self._values.items()}

    @Property(bool, notify=valuesChanged)
    def currentDangerous(self) -> bool:
        return is_dangerous(self._current, self._values)

    @Property(list, notify=jobsChanged)
    def jobs(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self.queue.records[:100]]

    @Property(str, notify=logChanged)
    def currentLog(self) -> str:
        return self.queue.current.log if self.queue.current else self._selected_log

    @Property(bool, notify=jobsChanged)
    def running(self) -> bool:
        return self.queue.current is not None

    @Property(str, notify=localeChanged)
    def locale(self) -> str:
        return self._locale

    @Property(dict, notify=localeChanged)
    def texts(self) -> dict[str, str]:
        return TEXTS.get(self._locale, TEXTS["en"])

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(dict, notify=resultChanged)
    def currentResult(self) -> dict[str, Any]:
        return self._result

    @Property(bool, notify=settingsChanged)
    def darkMode(self) -> bool:
        return self._dark_mode

    @Property(str, notify=settingsChanged)
    def logLevel(self) -> str:
        return str(self.settings.value("logLevel", "info"))

    @Property(str, notify=settingsChanged)
    def offlinePath(self) -> str:
        return self._offline_path

    @Slot(str)
    def selectCommand(self, name: str) -> None:
        if name not in self._by_name or self._current.name == name:
            return
        self._current = self._by_name[name]
        self._reset_values()
        self.currentCommandChanged.emit()

    @Slot(str, result=bool)
    def selectBySearch(self, query: str) -> bool:
        normalized = query.strip().lower()
        if not normalized:
            return False
        match = next(
            (
                spec
                for spec in self._catalog
                if normalized in spec.name.lower()
                or normalized in spec.title.lower()
                or normalized in spec.help.lower()
            ),
            None,
        )
        if match is None:
            self._set_status(f"No command matches: {query}")
            return False
        self.selectCommand(match.name)
        return True

    @Slot(str, object)
    def setValue(self, name: str, value: Any) -> None:
        self._values[name] = value
        self._revision += 1
        self.valuesChanged.emit()

    @Slot(str, result=object)
    def value(self, name: str) -> Any:
        value = self._values.get(name)
        return "" if value is None else value

    @Slot(str, result=str)
    def textValue(self, name: str) -> str:
        value = self._values.get(name)
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        return str(value)

    @Slot(str, result=bool)
    def boolValue(self, name: str) -> bool:
        return bool(self._values.get(name))

    @Slot(str, result=str)
    def text(self, key: str) -> str:
        return TEXTS.get(self._locale, TEXTS["en"]).get(key, key)

    @Slot(str)
    def setLocale(self, locale: str) -> None:
        if locale not in TEXTS or locale == self._locale:
            return
        self._locale = locale
        self.settings.setValue("locale", locale)
        self._status = TEXTS[locale]["ready"]
        self.localeChanged.emit()
        self.currentCommandChanged.emit()
        self.statusChanged.emit()

    @Slot(bool)
    def setDarkMode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        self.settings.setValue("darkMode", enabled)
        self.settingsChanged.emit()

    @Slot(str)
    def setLogLevel(self, level: str) -> None:
        if level not in {"debug", "info", "warning", "error"}:
            return
        self.settings.setValue("logLevel", level)
        self.settingsChanged.emit()

    @Slot()
    def chooseOfflinePath(self) -> None:
        path = QFileDialog.getExistingDirectory(None, "Select offline tools directory")
        if path:
            self.setOfflinePath(path)

    @Slot(str, result=bool)
    def setOfflinePath(self, path: str) -> bool:
        target = Path(path)
        if not target.is_dir():
            self._set_status(f"Offline directory does not exist: {path}")
            return False
        try:
            from health_tools.config import load_config
            from health_tools.core.offline import (
                merge_scanned_versions,
                save_offline_config,
                scan_versions,
            )

            config = load_config()
            versions = merge_scanned_versions(
                scan_versions(target), config.get("offline_versions", {})
            )
            save_offline_config(target, versions)
        except Exception as exc:
            self._set_status(str(exc))
            return False
        self._offline_path = str(target)
        self.settings.setValue("offlinePath", self._offline_path)
        self.settingsChanged.emit()
        self._set_status(f"Offline tools: {target}")
        return True

    @Slot(str, bool)
    def chooseFile(self, field_name: str, save: bool = False) -> None:
        if save:
            path, _ = QFileDialog.getSaveFileName(None, "Select output")
        else:
            path, _ = QFileDialog.getOpenFileName(None, "Select file")
        if path:
            self.setValue(field_name, path)

    @Slot(str)
    def chooseDirectory(self, field_name: str) -> None:
        path = QFileDialog.getExistingDirectory(None, "Select directory")
        if path:
            self.setValue(field_name, path)

    @Slot(bool, result=bool)
    def runCurrent(self, confirmed: bool = False) -> bool:
        issues = validate_values(self._current, self._values)
        if issues:
            issue = issues[0]
            self._set_status(issue.message_zh if self._locale == "zh_CN" else issue.message_en)
            return False
        if self.currentDangerous and not confirmed:
            self.dangerousConfirmationRequested.emit()
            return False
        log_level = str(self.settings.value("logLevel", "info"))
        argv = build_argv(self._current, self._values, log_level)
        output = self._output_path()
        request = JobRequest(self._current.name, argv, dict(self._values), output)
        self.queue.enqueue(request)
        self._set_status(f"Queued: {self._current.name}")
        return True

    @Slot(result=bool)
    def cancelCurrent(self) -> bool:
        return self.queue.cancel_current()

    @Slot(str)
    def retryJob(self, job_id: str) -> None:
        self.queue.retry(job_id)

    @Slot(str)
    def restoreJob(self, job_id: str) -> None:
        record = next((item for item in self.queue.records if item.request.id == job_id), None)
        if record is None or record.request.command not in self._by_name:
            return
        self._current = self._by_name[record.request.command]
        self._values = dict(record.request.values)
        self._revision += 1
        self.currentCommandChanged.emit()
        self.valuesChanged.emit()

    @Slot(str)
    def openJobOutput(self, job_id: str) -> None:
        record = next((item for item in self.queue.records if item.request.id == job_id), None)
        if record is None or not record.request.output_path:
            return
        path = Path(record.request.output_path)
        target = path if path.is_dir() else path.parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    @Slot(str)
    def showJobResult(self, job_id: str) -> None:
        record = next((item for item in self.queue.records if item.request.id == job_id), None)
        if record is None:
            return
        self._result = read_result(record.request.output_path)
        self.resultChanged.emit()

    @Slot(str)
    def showJobLog(self, job_id: str) -> None:
        record = next((item for item in self.queue.records if item.request.id == job_id), None)
        if record is None:
            return
        self._selected_log = record.log
        self.logChanged.emit()

    def _reset_values(self) -> None:
        self._values = {field.name: field.default for field in self._current.fields}
        self._revision += 1
        self.valuesChanged.emit()

    def _output_path(self) -> str | None:
        for name in ("sort_output", "output_path", "output"):
            value = self._values.get(name)
            if value:
                return str(value)
        return None

    def _discover_offline_path(self) -> str:
        try:
            from health_tools.config import load_config

            configured = str(load_config().get("offline_tools_path", ""))
            if configured and Path(configured).is_dir():
                return configured
        except Exception:
            pass
        stored = str(self.settings.value("offlinePath", ""))
        if stored and Path(stored).is_dir():
            return stored
        app_dir = (
            Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
        )
        candidate = app_dir / "offline"
        if candidate.is_dir():
            return str(candidate)
        return ""

    def _set_status(self, status: str) -> None:
        self._status = status
        self.statusChanged.emit()

    def _job_finished(self, _job_id: str, succeeded: bool) -> None:
        self._set_status("Completed" if succeeded else "Failed")
        self.showJobResult(_job_id)


class RuleViewModel(QObject):
    documentChanged = Signal()
    validationChanged = Signal()
    statusChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._document = RuleDocument.from_source(_rule_template("config"), kind="config")
        self._issues: list[dict[str, str]] = []
        self._status = ""

    @Property(str, notify=documentChanged)
    def source(self) -> str:
        return self._document.source()

    @Property(str, notify=documentChanged)
    def path(self) -> str:
        return str(self._document.path or "")

    @Property(str, notify=documentChanged)
    def kind(self) -> str:
        return self._document.kind

    @Property(list, notify=documentChanged)
    def kinds(self) -> list[str]:
        return list(RULE_KINDS)

    @Property(list, notify=documentChanged)
    def entries(self) -> list[dict[str, Any]]:
        return self._document.visual_entries()

    @Property(list, notify=validationChanged)
    def issues(self) -> list[dict[str, str]]:
        return self._issues

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Slot()
    def openDialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "Open YAML", filter="YAML (*.yaml *.yml)")
        if path:
            self.openPath(path)

    @Slot(str)
    def openPath(self, path: str) -> None:
        try:
            self._document = RuleDocument.load(Path(path))
            self._set_status(f"Opened {path}")
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str)
    def newDocument(self, kind: str) -> None:
        template = _rule_template(kind)
        self._document = RuleDocument.from_source(template, kind=kind)
        self._set_status(f"New {kind} rule")
        self.documentChanged.emit()
        self.validate()

    @Slot(str)
    def setSource(self, source: str) -> None:
        issues = self._document.replace_source(source)
        self._issues = [issue.to_dict() for issue in issues]
        self.validationChanged.emit()
        self.documentChanged.emit()

    @Slot()
    def validate(self) -> None:
        self._issues = [issue.to_dict() for issue in self._document.validate()]
        self.validationChanged.emit()
        self._set_status("Validation passed" if not self._issues else "Validation failed")

    @Slot(str, str)
    def setVisualValue(self, pointer: str, value: str) -> None:
        try:
            self._document.set_value(pointer, value)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str, str, str)
    def addChild(self, pointer: str, key: str, value: str) -> None:
        try:
            self._document.add_child(pointer, key, value)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str)
    def removeEntry(self, pointer: str) -> None:
        try:
            self._document.remove(pointer)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot()
    def save(self) -> None:
        target = self._document.path
        if target is None:
            path, _ = QFileDialog.getSaveFileName(None, "Save YAML", filter="YAML (*.yaml)")
            if not path:
                return
            target = Path(path)
        try:
            if self._document.validate():
                self._set_status("Resolve validation errors before saving")
                return
            saved = self._document.save(target, overwrite=True)
            self._set_status(f"Saved {saved}")
            self.documentChanged.emit()
        except Exception as exc:
            self._set_status(str(exc))

    def _set_status(self, status: str) -> None:
        self._status = status
        self.statusChanged.emit()


def _rule_template(kind: str) -> str:
    templates = {
        "chip": (
            "version: '1.0'\nchip: new_chip\ncsv:\n"
            "  header_row: 1\n  data_start_row: 2\ncolumns: []\n"
        ),
        "parse": "version: '1.0'\ndescription: ''\nregex: ''\ncolumns: []\n",
        "classify": "version: '1.0'\nstructure:\n  default: unclassified\nrules: []\n",
        "convert": "version: '1.0'\ndescription: ''\ncolumn_mapping: {}\n",
        "evaluate": (
            "type: hr\nref_column: REF_RESULT0\npred_column: ALGO_RESULT0\n"
            "methods: []\nthresholds: []\n"
        ),
        "config": "rules_dir: ''\noffline_tools_path: ''\noffline_versions: {}\n",
    }
    return templates.get(kind, "{}\n")
