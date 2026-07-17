from __future__ import annotations

from collections.abc import Callable

from health_tools.api import ConfigAction, ConfigRequest, ConfigResult, GHealthError, run_config


class HealthConfigService:
    def __init__(
        self,
        runner: Callable[[ConfigRequest], ConfigResult] = run_config,
    ) -> None:
        self._runner = runner
        self.warning = ""

    def initialize_and_sync(self) -> ConfigResult:
        self.warning = ""
        shown = self._runner(ConfigRequest(ConfigAction.SHOW))
        if shown.revision is None:
            self._runner(ConfigRequest(ConfigAction.INIT))
            shown = self._runner(ConfigRequest(ConfigAction.SHOW))
        try:
            shown = self._runner(ConfigRequest(ConfigAction.SCAN_OFFLINE))
            if not shown.config.get("offline_versions"):
                self.warning = "离线算法目录中未发现可用版本，请在设置中选择正确目录"
        except GHealthError as exc:
            self.warning = f"离线算法版本尚未同步：{exc}"
        return shown

    def show(self) -> ConfigResult:
        return self._runner(ConfigRequest(ConfigAction.SHOW))

    def save(self, source: str, expected_revision: str | None) -> ConfigResult:
        return self._runner(
            ConfigRequest(
                ConfigAction.REPLACE,
                source=source,
                expected_revision=expected_revision,
            )
        )

    def set_offline_path(self, path: str) -> ConfigResult:
        return self._runner(ConfigRequest(ConfigAction.SET_OFFLINE_PATH, value=path))
