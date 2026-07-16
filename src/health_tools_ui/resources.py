from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal
from ruamel.yaml import YAML

RULE_TYPES = ("chip", "parse", "classify", "convert", "evaluate")


@dataclass(frozen=True, slots=True)
class RuleAsset:
    kind: str
    variant: str
    name: str
    path: Path
    source: str
    writable: bool
    overrides_builtin: bool = False

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
        auto_initialize: bool = True,
        config_file: Path | None = None,
        default_rules_dir: Path | None = None,
        builtin_rules_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        from health_tools import config as health_config
        from health_tools.rules.loader import RuleLoader

        self.config_file = config_file or health_config.CONFIG_FILE
        self.default_rules_dir = default_rules_dir or health_config.DEFAULT_RULES_DIR
        self.builtin_rules_dir = builtin_rules_dir or RuleLoader.get_builtin_rules_path()
        self._assets: list[RuleAsset] = []
        self.error = ""
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule_refresh)
        self._watcher.directoryChanged.connect(self._schedule_refresh)
        if auto_initialize and config_file is None and not self.config_file.exists():
            health_config.init_config_dir()
            health_config.sync_builtin_rules(force=False)
        self.refresh()

    @property
    def user_rules_dir(self) -> Path | None:
        if not self.config_file.exists():
            return self.default_rules_dir if self.default_rules_dir.is_dir() else None
        try:
            yaml = YAML(typ="safe")
            data = yaml.load(self.config_file.read_text(encoding="utf-8")) or {}
            configured = Path(str(data.get("rules_dir", self.default_rules_dir))).expanduser()
            return configured if configured.is_dir() else None
        except Exception as exc:
            self.error = f"规则配置读取失败: {exc}"
            return None

    @property
    def assets(self) -> tuple[RuleAsset, ...]:
        return tuple(self._assets)

    def refresh(self) -> None:
        self.error = ""
        user_root = self.user_rules_dir
        if self.config_file.exists() and user_root is None and not self.error:
            self.error = "配置的规则目录不存在，当前仅显示内置规则"
        builtin_names = {
            (kind, path.name)
            for kind in RULE_TYPES
            for path in (self.builtin_rules_dir / kind).glob("*.yaml")
        }
        assets: list[RuleAsset] = []
        for kind in RULE_TYPES:
            user_files = list((user_root / kind).glob("*.yaml")) if user_root else []
            user_names = {path.name for path in user_files}
            for path in sorted(user_files, key=lambda item: item.name.lower()):
                assets.append(
                    RuleAsset(
                        kind,
                        _detect_variant(kind, path),
                        path.name,
                        path,
                        "user",
                        True,
                        (kind, path.name) in builtin_names,
                    )
                )
            builtin_dir = self.builtin_rules_dir / kind
            for path in sorted(builtin_dir.glob("*.yaml"), key=lambda item: item.name.lower()):
                if path.name not in user_names:
                    assets.append(
                        RuleAsset(
                            kind,
                            _detect_variant(kind, path),
                            path.name,
                            path,
                            "builtin",
                            False,
                        )
                    )
        self._assets = assets
        self._reset_watch_paths(user_root)
        self.changed.emit()

    def choices(
        self, provider: str, *, absolute: bool = False, patterns_only: bool = False
    ) -> list[dict[str, Any]]:
        if provider == "all_rules":
            selected = [asset for asset in self._assets if asset.kind != "chip"]
            return [asset.to_dict(absolute=True) for asset in selected]
        selected = [asset for asset in self._assets if asset.kind == provider]
        if patterns_only:
            selected = [asset for asset in selected if asset.variant == "patterns"]
        return [asset.to_dict(absolute=absolute) for asset in selected]

    def destination(self, kind: str, name: str) -> Path:
        if kind not in RULE_TYPES:
            raise ValueError(f"Unsupported rule type: {kind}")
        safe_name = Path(name.strip()).name
        if safe_name != name.strip() or safe_name in {"", ".", ".."}:
            raise ValueError("规则名称只能包含文件名，不能包含目录")
        if not safe_name.lower().endswith((".yaml", ".yml")):
            safe_name += ".yaml"
        root = self.user_rules_dir
        if root is None:
            raise ValueError(self.error or "用户规则目录不可用")
        return root / kind / safe_name

    def _schedule_refresh(self, _path: str) -> None:
        QTimer.singleShot(120, self.refresh)

    def _reset_watch_paths(self, user_root: Path | None) -> None:
        current = self._watcher.files() + self._watcher.directories()
        if current:
            self._watcher.removePaths(current)
        paths = [self.config_file]
        if user_root:
            paths.extend(user_root / kind for kind in RULE_TYPES)
        existing = [str(path) for path in paths if path.exists()]
        if existing:
            self._watcher.addPaths(existing)


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
        config_loader: Callable[[], dict[str, Any]] | None = None,
        exe_finder: Callable[[str, str | None], Path | None] | None = None,
    ) -> None:
        if config_loader is None:
            from health_tools.config import load_config

            config_loader = load_config
        if exe_finder is None:
            from health_tools.core.offline import find_exe

            exe_finder = find_exe
        self._config_loader = config_loader
        self._exe_finder = exe_finder

    def chips(self) -> list[dict[str, Any]]:
        versions = self._config_loader().get("offline_versions", {})
        return [
            {"key": str(chip), "value": str(chip), "label": str(chip), "enabled": True}
            for chip in sorted(versions)
        ]

    def versions(self, chip: str, *, allow_missing: bool = False) -> list[dict[str, Any]]:
        config = self._config_loader().get("offline_versions", {})
        chip_config = config.get(chip, {}) if isinstance(config, dict) else {}
        default = chip_config.get("default", "") if isinstance(chip_config, dict) else ""
        raw = chip_config.get("versions", {}) if isinstance(chip_config, dict) else {}
        pairs: list[tuple[str, str]] = []
        if isinstance(raw, dict):
            for category, items in raw.items():
                if isinstance(items, list):
                    pairs.extend((str(category), str(item)) for item in items)
        elif isinstance(raw, list):
            pairs.extend(("exclusive", str(item)) for item in raw)
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for category, version in pairs:
            if version in seen:
                continue
            seen.add(version)
            item = OfflineVersion(
                chip,
                category,
                version,
                version == default,
                self._exe_finder(chip, version) is not None,
            )
            result.append(item.to_dict(allow_missing=allow_missing))
        return result


def _detect_variant(kind: str, path: Path) -> str:
    if kind != "classify":
        return kind
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
        if "patterns" in data and not ({"structure", "classify", "rules"} & set(data)):
            return "patterns"
    except Exception:
        pass
    return "classify"
