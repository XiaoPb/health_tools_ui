from __future__ import annotations

from health_tools.api import ConfigAction, ConfigResult, RequestValidationError

from health_tools_ui.config_service import HealthConfigService


class FakeConfigApi:
    def __init__(self, *, versions=None, scan_error: str = "") -> None:
        self.source = "rules_dir: first\n"
        self.revision = "r1"
        self.versions = (
            {"gh3036": {"versions": {"exclusive": ["v1"]}}}
            if versions is None
            else versions
        )
        self.scan_error = scan_error
        self.actions = []

    def __call__(self, request):
        self.actions.append(request.action)
        if request.action == ConfigAction.REPLACE:
            if request.expected_revision != self.revision:
                raise RequestValidationError("配置 revision 冲突")
            self.source = request.source
            self.revision = "r2"
        elif request.action == ConfigAction.SCAN_OFFLINE:
            if self.scan_error:
                raise RequestValidationError(self.scan_error)
            self.versions = {"gh3036": {"versions": {"exclusive": ["v1"]}}}
        return ConfigResult(
            request.action,
            {"rules_dir": "first", "offline_versions": self.versions},
            source=self.source,
            revision=self.revision,
        )


def test_config_service_reads_public_snapshot() -> None:
    api = FakeConfigApi()
    result = HealthConfigService(api).initialize_and_sync()
    assert result.source == "rules_dir: first\n"
    assert result.revision == "r1"
    assert ConfigAction.SCAN_OFFLINE in api.actions


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


def test_config_service_scans_when_versions_are_empty() -> None:
    api = FakeConfigApi(versions={})
    service = HealthConfigService(api)

    result = service.initialize_and_sync()

    assert ConfigAction.SCAN_OFFLINE in api.actions
    assert result.config["offline_versions"]
    assert service.warning == ""


def test_config_service_explains_scan_failure() -> None:
    api = FakeConfigApi(versions={}, scan_error="目录无效")
    service = HealthConfigService(api)

    result = service.initialize_and_sync()

    assert result.config["offline_versions"] == {}
    assert "目录无效" in service.warning
