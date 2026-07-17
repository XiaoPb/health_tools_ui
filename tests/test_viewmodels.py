from __future__ import annotations

import math

from health_tools.api import ConfigAction, ConfigResult, RequestValidationError, RuleCatalogResult
from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy

from health_tools_ui.config_service import HealthConfigService
from health_tools_ui.resources import RuleCatalogService
from health_tools_ui.viewmodels import AppViewModel, RuleViewModel


class FakeConfigApi:
    def __init__(self, source: str) -> None:
        self.source = source
        self.revision = "r1"
        self.replace_count = 0

    def __call__(self, request):
        if request.action == ConfigAction.REPLACE:
            if request.expected_revision != self.revision:
                raise RequestValidationError("配置 revision 冲突")
            self.source = request.source
            self.revision = f"r{int(self.revision[1:]) + 1}"
            self.replace_count += 1
        return ConfigResult(request.action, source=self.source, revision=self.revision)


def config_model(source: str) -> tuple[RuleViewModel, FakeConfigApi]:
    api = FakeConfigApi(source)
    catalog = RuleCatalogService(list_runner=lambda _request: RuleCatalogResult())
    return RuleViewModel(rule_catalog=catalog, config_service=HealthConfigService(api)), api


def test_offline_version_modes_map_to_original_click_fields(qapp, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    model = AppViewModel(settings)
    model.selectCommand("offline")

    model.setOfflineVersionMode("selected")
    model.setOfflineVersions(["v1"])
    assert model.value("ver") == "v1"
    assert model.value("versions") == ""

    model.setOfflineVersions(["v2", "v1", "v2"])
    assert model.value("ver") == ""
    assert model.value("versions") == "v2,v1"

    model.setOfflineVersionMode("all")
    assert model.boolValue("all_versions") is True
    assert model.value("versions") == ""


def test_non_finite_command_numbers_are_rejected(qapp, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    model = AppViewModel(settings)

    model.selectCommand("plot")
    original_number = model.value("sample_rate")
    for value in (math.nan, math.inf, -math.inf):
        model.setNumericValue("sample_rate", value)
        assert model.value("sample_rate") == original_number

    model.selectCommand("info")
    original_integer = model.value("preview")
    for value in (math.nan, math.inf, -math.inf):
        model.setNumericValue("preview", value)
        assert model.value("preview") == original_integer


def test_config_reloads_from_user_file_when_opened(qapp, tmp_path) -> None:
    model, api = config_model("rules_dir: first\n")
    api.source = "rules_dir: second\n"
    api.revision = "r2"
    model.requestOpenConfig()

    assert model.kind == "config"
    assert model.selectedNode["kind"] == "mapping"
    model.selectNode("/rules_dir")
    assert model.selectedNode["rawValue"] == "second"
    assert model.dirty is False


def test_config_save_rejects_external_changes(qapp, tmp_path) -> None:
    model, api = config_model("rules_dir: original\nretries: 5\n")

    model.setVisualValue("/rules_dir", "draft")
    api.source = "rules_dir: external\nretries: 5\n"
    api.revision = "r2"
    model.save()

    assert api.source.startswith("rules_dir: external")
    assert model.dirty is True
    assert "extern" in model.status.lower() or "外部" in model.status


def test_equal_config_edit_and_clean_save_do_not_write(qapp, tmp_path) -> None:
    original = "rules_dir: original\n"
    model, api = config_model(original)
    changed = QSignalSpy(model.documentChanged)

    model.setVisualValue("/rules_dir", "original")
    model.save()

    assert changed.count() == 0
    assert model.dirty is False
    assert api.source == original
    assert api.replace_count == 0


def test_non_finite_rule_number_is_rejected(qapp, tmp_path) -> None:
    model, _api = config_model("rules_dir: original\nretries: 5\n")

    for value in (math.nan, math.inf, -math.inf):
        model.setVisualNumber("/retries", value)
        model.selectNode("/retries")
        assert model.selectedNode["rawValue"] == 5
        assert model.dirty is False
