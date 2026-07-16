from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QSettings, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from .arguments import build_argv, is_dangerous, validate_values
from .catalog import build_catalog
from .config_service import HealthConfigService
from .csv_inference import infer_csv_columns
from .history import HistoryStore
from .models import CommandSpec, JobRequest
from .resources import OfflineCatalogService, RuleCatalogService
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
    "do_list": "仅列出芯片与版本",
    "no_run": "仅处理已有结果",
    "no_accuracy": "跳过准确度统计",
    "no_plot": "跳过 PSD 绘图",
    "hba_fs": "采样率",
    "scene_en": "场景适配",
    "ch_num": "有效 PPG 通道数",
    "ref_col": "金标列索引",
    "ppg_offset": "PPG 通道偏移",
    "ppg_maps": "PPG 通道映射",
    "settle_timeout": "输出稳定等待时间",
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

    def __init__(
        self,
        settings: QSettings,
        parent: QObject | None = None,
        rule_catalog: RuleCatalogService | None = None,
    ) -> None:
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
        self.rule_catalog = rule_catalog or RuleCatalogService(self)
        self.offline_catalog = OfflineCatalogService()
        self._offline_mode = "default"
        self._offline_selected_versions: list[str] = []
        self.rule_catalog.changed.connect(self._choices_changed)
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
            if self._current.name == "offline" and field.name in {
                "ver",
                "versions",
                "all_versions",
            }:
                continue
            item = field.to_dict()
            if item["default"] is None:
                item["default"] = ""
            if self._locale == "zh_CN":
                item["label"] = ZH_FIELD_LABELS.get(field.name, field.label)
            else:
                option = field.flags[0] if field.flags else field.name
                item["help"] = f"ghealth-tools option: {option}"
            provider = field.choice_provider
            if provider:
                choices = self._choices_for_provider(provider)
                current = self._values.get(field.name)
                current_values = current if isinstance(current, (list, tuple)) else [current]
                known = {choice["value"] for choice in choices}
                for value in current_values:
                    if value not in (None, "") and value not in known:
                        choices.append(
                            {
                                "key": str(value),
                                "value": str(value),
                                "label": f"{Path(str(value)).name} · 外部",
                                "enabled": True,
                            }
                        )
                item["choices"] = choices
                item["kind"] = "multi_choice" if field.multiple else "choice"
            fields.append(item)
        return fields

    @Property(str, notify=valuesChanged)
    def offlineVersionMode(self) -> str:
        return self._offline_mode

    @Property(list, notify=valuesChanged)
    def offlineVersionChoices(self) -> list[dict[str, Any]]:
        return self._offline_version_choices()

    def _offline_version_choices(self) -> list[dict[str, Any]]:
        chip = str(self._values.get("chip_name") or "")
        return (
            self.offline_catalog.versions(chip, allow_missing=bool(self._values.get("no_run")))
            if chip
            else []
        )

    @Property(list, notify=valuesChanged)
    def offlineSelectedVersions(self) -> list[str]:
        return list(self._offline_selected_versions)

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
        if self._current.name == "offline" and name in {"chip_name", "no_run"}:
            available = {item["value"] for item in self._offline_version_choices()}
            self._offline_selected_versions = [
                version for version in self._offline_selected_versions if version in available
            ]
        self._revision += 1
        self.valuesChanged.emit()

    @Slot(str, float)
    def setNumericValue(self, name: str, value: float) -> None:
        if not math.isfinite(value):
            self.refreshValues()
            return
        field = next((item for item in self._current.fields if item.name == name), None)
        normalized: int | float = int(value) if field and field.kind.value == "integer" else value
        self.setValue(name, normalized)

    @Slot()
    def refreshValues(self) -> None:
        self._revision += 1
        self.valuesChanged.emit()

    @Slot(str)
    def setOfflineVersionMode(self, mode: str) -> None:
        if mode not in {"default", "selected", "all"}:
            return
        self._offline_mode = mode
        self._apply_offline_versions()

    @Slot(list)
    def setOfflineVersions(self, versions: list[Any]) -> None:
        seen: set[str] = set()
        self._offline_selected_versions = []
        for item in versions:
            value = str(item)
            if value and value not in seen:
                self._offline_selected_versions.append(value)
                seen.add(value)
        self._apply_offline_versions()

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

    @Slot(str)
    def browseDynamicField(self, field_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(None, "选择 YAML", filter="YAML (*.yaml *.yml)")
        if path:
            field = next((item for item in self._current.fields if item.name == field_name), None)
            if field and field.multiple:
                current = self._values.get(field_name)
                values = list(current) if isinstance(current, (list, tuple)) else []
                if path not in values:
                    values.append(path)
                self.setValue(field_name, values)
            else:
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
        self._offline_mode = "default"
        self._offline_selected_versions = []
        self.valuesChanged.emit()

    def _choices_changed(self) -> None:
        self.currentCommandChanged.emit()

    def _choices_for_provider(self, provider: str) -> list[dict[str, Any]]:
        if provider == "offline_chips":
            rule_chips = {item["value"]: item for item in self.rule_catalog.choices("chip")}
            result: list[dict[str, Any]] = []
            for item in self.offline_catalog.chips():
                if item["value"] not in rule_chips:
                    item = dict(item)
                    item["label"] += " · 缺少芯片规则"
                result.append(item)
            for value, item in rule_chips.items():
                if not any(existing["value"] == value for existing in result):
                    result.append(item)
            return result
        if provider == "classify_patterns":
            return self.rule_catalog.choices("classify", patterns_only=True)
        return self.rule_catalog.choices(provider, absolute=provider == "all_rules")

    def _apply_offline_versions(self) -> None:
        self._values["ver"] = None
        self._values["versions"] = None
        self._values["all_versions"] = self._offline_mode == "all"
        if self._offline_mode == "selected":
            if len(self._offline_selected_versions) == 1:
                self._values["ver"] = self._offline_selected_versions[0]
            elif len(self._offline_selected_versions) > 1:
                self._values["versions"] = ",".join(self._offline_selected_versions)
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
    saveNameRequested = Signal()
    saveConflict = Signal(str)
    externalConflict = Signal(str)
    selectionChanged = Signal()
    discardConfirmationRequested = Signal(str, str)

    def __init__(
        self,
        parent: QObject | None = None,
        rule_catalog: RuleCatalogService | None = None,
        config_service: HealthConfigService | None = None,
    ) -> None:
        super().__init__(parent)
        self.rule_catalog = rule_catalog or RuleCatalogService(self)
        self.config_service = config_service or HealthConfigService()
        self.rule_catalog.changed.connect(self.documentChanged)
        config_path = self.config_service.initialize_and_sync()
        self._document = (
            RuleDocument.load(config_path, kind="config")
            if config_path.exists()
            else RuleDocument.from_source(_rule_template("config"), kind="config")
        )
        self._issues: list[dict[str, str]] = []
        self._status = ""
        self._selected_pointer = ""
        self._expanded_pointers: set[str] = set()

    @Property(str, notify=documentChanged)
    def source(self) -> str:
        return self._document.editor_source()

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

    @Property(list, notify=documentChanged)
    def tree(self) -> list[dict[str, Any]]:
        return self._document.tree_nodes()

    @Property(str, notify=documentChanged)
    def selectedPointer(self) -> str:
        return self._selected_pointer

    @Property(dict, notify=selectionChanged)
    def selectedNode(self) -> dict[str, Any]:
        try:
            return self._document.node(self._selected_pointer)
        except Exception:
            return self._document.node("")

    @Property(list, notify=selectionChanged)
    def availableKeys(self) -> list[dict[str, Any]]:
        try:
            return self._document.available_keys(self._selected_pointer)
        except Exception:
            return []

    @Property(bool, notify=selectionChanged)
    def canAddListItem(self) -> bool:
        try:
            return self._document.node(self._selected_pointer).get("kind") == "list"
        except Exception:
            return False

    @Property(bool, notify=documentChanged)
    def dirty(self) -> bool:
        return self._document.dirty

    @Property(list, notify=documentChanged)
    def availableRules(self) -> list[dict[str, Any]]:
        kind = self._document.kind
        if kind == "config":
            return []
        return self.rule_catalog.choices(kind)

    @Property(list, notify=documentChanged)
    def expandedPointers(self) -> list[str]:
        return sorted(self._expanded_pointers)

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
            self.requestOpenPath(path)

    @Slot(str)
    def requestOpenPath(self, path: str) -> None:
        if self._document.dirty:
            self.discardConfirmationRequested.emit("open", path)
        else:
            self.openPath(path)

    @Slot()
    def requestOpenConfig(self) -> None:
        if self._document.dirty:
            self.discardConfirmationRequested.emit("config", "")
        else:
            self.openConfig()

    @Slot()
    def openConfig(self) -> None:
        try:
            config_path = self.config_service.initialize_and_sync()
            self._document = RuleDocument.load(config_path, kind="config")
            self._selected_pointer = ""
            self._expanded_pointers = set(_container_pointers(self._document)[:2])
            self._set_status(f"Opened {config_path}")
            self.documentChanged.emit()
            self.selectionChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str)
    def openPath(self, path: str) -> None:
        try:
            self._document = RuleDocument.load(Path(path))
            self._selected_pointer = ""
            self._expanded_pointers = set(_container_pointers(self._document)[:2])
            self._set_status(f"Opened {path}")
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str)
    def newDocument(self, kind: str) -> None:
        template = _rule_template(kind)
        self._document = RuleDocument.from_source(template, kind=kind)
        self._selected_pointer = ""
        self._expanded_pointers = set(_container_pointers(self._document)[:2])
        self._set_status(f"New {kind} rule")
        self.documentChanged.emit()
        self.validate()

    @Slot(str)
    def requestNewDocument(self, kind: str) -> None:
        if self._document.dirty:
            self.discardConfirmationRequested.emit("new", kind)
        else:
            self.newDocument(kind)

    @Slot(str, str)
    def confirmDiscard(self, action: str, payload: str) -> None:
        if action == "open":
            self.openPath(payload)
        elif action == "new":
            self.newDocument(payload)
        elif action == "config":
            self.openConfig()

    @Slot()
    def reloadExternal(self) -> None:
        if self._document.kind == "config":
            self.openConfig()
        elif self._document.path is not None:
            self.openPath(str(self._document.path))

    @Slot(str)
    def setSource(self, source: str) -> None:
        if source == self._document.editor_source():
            return
        issues = self._document.replace_source(source)
        self._issues = [issue.to_dict() for issue in issues]
        self.validationChanged.emit()
        self.documentChanged.emit()
        self.selectionChanged.emit()

    @Slot(str)
    def selectNode(self, pointer: str) -> None:
        self._selected_pointer = pointer
        self.selectionChanged.emit()

    @Slot(str, bool)
    def setNodeExpanded(self, pointer: str, expanded: bool) -> None:
        if expanded:
            self._expanded_pointers.add(pointer)
        else:
            self._expanded_pointers.discard(pointer)

    @Slot(bool)
    def setAllExpanded(self, expanded: bool) -> None:
        self._expanded_pointers = set(_container_pointers(self._document)) if expanded else set()
        self.documentChanged.emit()

    @Slot()
    def validate(self) -> None:
        self._issues = [issue.to_dict() for issue in self._document.validate()]
        self.validationChanged.emit()
        self._set_status(
            "验证通过 / Validation passed"
            if not self._issues
            else "验证失败 / Validation failed"
        )

    @Slot(str, str)
    def setVisualValue(self, pointer: str, value: str) -> None:
        try:
            if self._document.set_value(pointer, value):
                self.documentChanged.emit()
                self.selectionChanged.emit()
                self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str, float)
    def setVisualNumber(self, pointer: str, value: float) -> None:
        if not math.isfinite(value):
            self.refreshDocument()
            return
        try:
            current = self._document.node(pointer).get("rawValue")
            source = (
                str(int(value))
                if isinstance(current, int) and not isinstance(current, bool)
                else repr(value)
            )
            if self._document.set_value(pointer, source):
                self.documentChanged.emit()
                self.selectionChanged.emit()
                self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot()
    def refreshDocument(self) -> None:
        self.documentChanged.emit()
        self.selectionChanged.emit()

    @Slot(str, str, str)
    def addChild(self, pointer: str, key: str, value: str) -> None:
        try:
            self._document.add_child(pointer, key, value)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str)
    def addSuggested(self, key: str) -> None:
        try:
            self._document.add_suggested(self._selected_pointer, key)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str, str)
    def addCustom(self, key: str, value: str) -> None:
        self.addChild(self._selected_pointer, key, value)

    @Slot()
    def addListItem(self) -> None:
        try:
            self._document.add_list_item(self._selected_pointer)
            self.documentChanged.emit()
            self.validate()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str, int)
    def moveEntry(self, pointer: str, offset: int) -> None:
        try:
            self._document.move_list_item(pointer, offset)
            self.documentChanged.emit()
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
        if not self._document.dirty:
            self._set_status("没有实际修改 / No actual changes")
            return
        if self._document.kind == "config":
            try:
                if self._document.validate():
                    self._set_status("Resolve validation errors before saving")
                    return
                if self._document.has_external_changes(self.config_service.user_config):
                    self._set_status("配置文件已被外部修改 / Config changed externally")
                    self.externalConflict.emit(str(self.config_service.user_config))
                    return
                saved = self.config_service.save(self._document.source())
                self._document = RuleDocument.load(saved, kind="config")
                self.rule_catalog.refresh()
                suffix = f" ({self.config_service.warning})" if self.config_service.warning else ""
                self._set_status(f"Saved {saved}{suffix}")
                self.documentChanged.emit()
            except Exception as exc:
                self._set_status(str(exc))
            return
        target = self._document.path
        user_root = self.rule_catalog.user_rules_dir
        writable_user_file = bool(
            target and user_root and target.is_relative_to(user_root) and target.exists()
        )
        if not writable_user_file:
            self.saveNameRequested.emit()
            return
        try:
            if self._document.validate():
                self._set_status("Resolve validation errors before saving")
                return
            if self._document.has_external_changes(target):
                self._set_status("规则文件已被外部修改 / Rule changed externally")
                self.externalConflict.emit(str(target))
                return
            saved = self._document.save(target, overwrite=True)
            self._set_status(f"Saved {saved}")
            self.documentChanged.emit()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot(str, bool)
    def saveToLibrary(self, name: str, overwrite: bool = False) -> None:
        try:
            if self._document.kind == "config":
                self._set_status("全局配置请通过 Config 命令保存")
                return
            target = self.rule_catalog.destination(self._document.kind, name)
            if target.exists() and not overwrite:
                self.saveConflict.emit(str(target))
                return
            if self._document.validate():
                self._set_status("Resolve validation errors before saving")
                return
            saved = self._document.save(target, overwrite=overwrite)
            self.rule_catalog.refresh()
            self._set_status(f"Saved {saved}")
            self.documentChanged.emit()
        except Exception as exc:
            self._set_status(str(exc))

    @Slot()
    def inferCsvColumns(self) -> None:
        if self._document.kind not in {"parse", "convert"}:
            return
        path, _ = QFileDialog.getOpenFileName(None, "选择 CSV", filter="CSV (*.csv);;所有文件 (*)")
        if not path:
            return
        inferred = infer_csv_columns(Path(path))
        if inferred is None:
            self._set_status("首行和第二行均未读取到有效列名，已跳过")
            return
        self._document.apply_inferred_columns(list(inferred.columns))
        self._set_status(
            f"从第 {inferred.row} 行推断 {len(inferred.columns)} 个列名 ({inferred.encoding})"
        )
        self.documentChanged.emit()
        self.validate()

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


def _container_pointers(document: RuleDocument) -> list[str]:
    return [
        entry["pointer"]
        for entry in document.visual_entries()
        if entry["kind"] in {"mapping", "list"}
    ]
