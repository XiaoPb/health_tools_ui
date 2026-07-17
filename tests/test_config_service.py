from __future__ import annotations

from health_tools.api import ConfigAction, ConfigResult, RequestValidationError

from health_tools_ui.config_service import HealthConfigService


class FakeConfigApi:
    def __init__(self) -> None:
        self.source = "rules_dir: first\n"
        self.revision = "r1"

    def __call__(self, request):
        if request.action == ConfigAction.REPLACE:
            if request.expected_revision != self.revision:
                raise RequestValidationError("配置 revision 冲突")
            self.source = request.source
            self.revision = "r2"
        return ConfigResult(
            request.action, {"rules_dir": "first"}, source=self.source, revision=self.revision
        )


def test_config_service_reads_public_snapshot() -> None:
    api = FakeConfigApi()
    result = HealthConfigService(api).initialize_and_sync()
    assert result.source == "rules_dir: first\n"
    assert result.revision == "r1"


def test_config_service_replaces_with_revision() -> None:
    api = FakeConfigApi()
    result = HealthConfigService(api).save("rules_dir: changed\n", "r1")
    assert result.source == "rules_dir: changed\n"
    assert result.revision == "r2"


def test_config_service_surfaces_revision_conflict() -> None:
    api = FakeConfigApi()
    try:
        HealthConfigService(api).save("rules_dir: lost\n", "stale")
    except RequestValidationError as exc:
        assert "revision" in str(exc)
    else:
        raise AssertionError("stale revision was accepted")
