from __future__ import annotations

from collections.abc import Callable

from health_tools.api import ConfigAction, ConfigRequest, ConfigResult, run_config


class HealthConfigService:
    def __init__(
        self,
        runner: Callable[[ConfigRequest], ConfigResult] = run_config,
    ) -> None:
        self._runner = runner
        self.warning = ""

    def initialize_and_sync(self) -> ConfigResult:
        shown = self._runner(ConfigRequest(ConfigAction.SHOW))
        if shown.revision is None:
            self._runner(ConfigRequest(ConfigAction.INIT))
            shown = self._runner(ConfigRequest(ConfigAction.SHOW))
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
