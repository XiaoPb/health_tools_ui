from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


class HealthConfigService:
    def __init__(
        self,
        user_config: Path | None = None,
        install_config: Path | None = None,
    ) -> None:
        from health_tools.config import CONFIG_FILE

        self.user_config = user_config or CONFIG_FILE
        self.install_config: Path | None
        if install_config is not None:
            self.install_config = install_config
        elif getattr(sys, "frozen", False):
            self.install_config = Path(sys.executable).resolve().parent / "config" / "config.yaml"
        else:
            self.install_config = None
        self.warning = ""

    def initialize_and_sync(self) -> Path:
        if not self.user_config.exists() and self.install_config and self.install_config.exists():
            self._atomic_copy(self.install_config, self.user_config)
        if not self.user_config.exists():
            from health_tools.config import init_config_dir, sync_builtin_rules

            init_config_dir()
            sync_builtin_rules(force=False)
        self.sync_install_copy()
        return self.user_config

    def sync_install_copy(self) -> bool:
        if not self.install_config or not self.user_config.exists():
            return False
        try:
            self._atomic_copy(self.user_config, self.install_config)
        except OSError as exc:
            self.warning = f"安装目录配置副本同步失败: {exc}"
            return False
        self.warning = ""
        return True

    def save(self, source: str) -> Path:
        self._atomic_write(self.user_config, source)
        self.sync_install_copy()
        self.invalidate_upstream_cache()
        return self.user_config

    @staticmethod
    def invalidate_upstream_cache() -> None:
        from health_tools import config as health_config

        health_config._config_cache = None

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        HealthConfigService._atomic_write_bytes(destination, source.read_bytes())

    @staticmethod
    def _atomic_write(destination: Path, source: str) -> None:
        HealthConfigService._atomic_write_bytes(destination, source.encode("utf-8"))

    @staticmethod
    def _atomic_write_bytes(destination: Path, source: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(source)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
