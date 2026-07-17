from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from health_tools.api import (
    OfflineCatalogRequest,
    OfflineCatalogResult,
    RuleCatalogResult,
    RuleInfo,
    RuleListRequest,
    RuleReadRequest,
    RuleType,
    run_list_rules,
    run_offline_catalog,
    run_read_rule,
)
from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal
from ruamel.yaml import YAML

RULE_TYPES = tuple(item.value for item in RuleType)


@dataclass(frozen=True, slots=True)
class RuleAsset:
    kind: str
    variant: str
    name: str
    path: Path
    source: str
    writable: bool
    overrides_builtin: bool = False
    revision: str = ""

    @property
    def value(self) -> str:
        return self.path.stem if self.kind == "chip" else self.name

    @property
    def label(self) -> str:
        origin = "用户" if self.source == "user" else "内置"
        suffix = " · 覆盖内置" if self.overrides_builtin else ""
        return f"{self.path.stem if self.kind == 'chip' else self.name} · {origin}{suffix}"

    def to_dict(self, *, absolute: bool = False) -> dict[str, Any]:
        result = asdict(self)
        result["path"] = str(self.path)
        result["value"] = str(self.path) if absolute else self.value
        result["label"] = self.label
        result["enabled"] = True
        result["key"] = result["value"]
        return result


class RuleCatalogService(QObject):
    changed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        list_runner: Callable[[RuleListRequest], RuleCatalogResult] = run_list_rules,
        read_runner: Callable[[RuleReadRequest], Any] = run_read_rule,
    ) -> None:
        super().__init__(parent)
        self._list_runner = list_runner
        self._read_runner = read_runner
        self._assets: list[RuleAsset] = []
        self.error = ""
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule_refresh)
        self._watcher.directoryChanged.connect(self._schedule_refresh)
        self.refresh()

    @property
    def assets(self) -> tuple[RuleAsset, ...]:
        return tuple(self._assets)

    def refresh(self) -> None:
        self.error = ""
        try:
            rules = self._list_runner(RuleListRequest()).rules
            self._assets = [self._asset(info) for info in rules]
            self._reset_watch_paths()
        except Exception as exc:
            self.error = f"规则目录读取失败: {exc}"
            self._assets = []
        self.changed.emit()

    def _asset(self, info: RuleInfo) -> RuleAsset:
        variant = info.rule_type.value
        revision = next((item.revision for item in info.variants if item.source == info.source), "")
        if info.rule_type == RuleType.CLASSIFY:
            try:
                document = self._read_runner(
                    RuleReadRequest(info.rule_type, info.name, info.source)
                )
                data = YAML(typ="safe").load(document.source) or {}
                if "patterns" in data and not ({"structure", "classify", "rules"} & set(data)):
                    variant = "patterns"
            except Exception:
                pass
        return RuleAsset(
            info.rule_type.value,
            variant,
            info.name,
            info.path,
            info.source.value,
            info.writable,
            info.overrides_builtin,
            revision,
        )

    def choices(
        self, provider: str, *, absolute: bool = False, patterns_only: bool = False
    ) -> list[dict[str, Any]]:
        selected = (
            [asset for asset in self._assets if asset.kind != "chip"]
            if provider == "all_rules"
            else [asset for asset in self._assets if asset.kind == provider]
        )
        if patterns_only:
            selected = [asset for asset in selected if asset.variant == "patterns"]
        return [asset.to_dict(absolute=absolute or provider == "all_rules") for asset in selected]

    def asset(self, kind: str, name: str) -> RuleAsset | None:
        return next(
            (item for item in self._assets if item.kind == kind and item.name == name), None
        )

    def _schedule_refresh(self, _path: str) -> None:
        QTimer.singleShot(120, self.refresh)

    def _reset_watch_paths(self) -> None:
        current = self._watcher.files() + self._watcher.directories()
        if current:
            self._watcher.removePaths(current)
        paths = {str(asset.path.parent) for asset in self._assets if asset.path.parent.exists()}
        if paths:
            self._watcher.addPaths(sorted(paths))


@dataclass(frozen=True, slots=True)
class OfflineVersion:
    chip: str
    category: str
    version: str
    is_default: bool
    executable_available: bool

    def to_dict(self, *, allow_missing: bool = False) -> dict[str, Any]:
        category = self.category or "默认"
        default = " · 默认" if self.is_default else ""
        missing = " · EXE缺失" if not self.executable_available else ""
        return {
            "key": self.version,
            "value": self.version,
            "label": f"{self.version} · {category}{default}{missing}",
            "category": self.category,
            "isDefault": self.is_default,
            "enabled": self.executable_available or allow_missing,
        }


class OfflineCatalogService:
    def __init__(
        self,
        runner: Callable[[OfflineCatalogRequest], OfflineCatalogResult] = run_offline_catalog,
    ) -> None:
        self._runner = runner

    def chips(self) -> list[dict[str, Any]]:
        values = sorted({item.chip_name for item in self._runner(OfflineCatalogRequest()).versions})
        return [{"key": value, "value": value, "label": value, "enabled": True} for value in values]

    def versions(self, chip: str, *, allow_missing: bool = False) -> list[dict[str, Any]]:
        values = self._runner(OfflineCatalogRequest(chip)).versions
        return [
            OfflineVersion(
                item.chip_name,
                item.category or "exclusive",
                item.version,
                item.is_default,
                item.exe_available,
            ).to_dict(allow_missing=allow_missing)
            for item in values
        ]
