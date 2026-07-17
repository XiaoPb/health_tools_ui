from __future__ import annotations

import math

from health_tools.api import ConfigAction, ConfigResult, RequestValidationError, RuleCatalogResult
from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy

from health_tools_ui.config_service import HealthConfigService
from health_tools_ui.resources import RuleCatalogService
from health_tools_ui.viewmodels import AppViewModel, ConfigViewModel, RuleViewModel


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


class StubConfigService:
    def __init__(self, offline_path: str) -> None:
        self.offline_path = offline_path
        self.warning = ""

    def show(self) -> ConfigResult:
        return ConfigResult(
            ConfigAction.SHOW,
            {"offline_tools_path": self.offline_path},
        )

    def set_offline_path(self, path: str) -> ConfigResult:
        self.offline_path = path
        return ConfigResult(
            ConfigAction.SET_OFFLINE_PATH,
            {"offline_tools_path": path},
        )


def config_model(source: str) -> tuple[ConfigViewModel, FakeConfigApi]:
    api = FakeConfigApi(source)
    return ConfigViewModel(config_service=HealthConfigService(api)), api


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


def test_app_model_uses_injected_configured_offline_path(qapp, tmp_path) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    model = AppViewModel(settings, config_service=StubConfigService(str(tools)))

    assert model.offlinePath == str(tools)


def test_setting_offline_path_refreshes_version_bindings(qapp, tmp_path) -> None:
    old_tools = tmp_path / "old"
    new_tools = tmp_path / "new"
    old_tools.mkdir()
    new_tools.mkdir()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    service = StubConfigService(str(old_tools))
    model = AppViewModel(settings, config_service=service)
    values_changed = QSignalSpy(model.valuesChanged)
    command_changed = QSignalSpy(model.currentCommandChanged)

    assert model.setOfflinePath(str(new_tools)) is True

    assert model.offlinePath == str(new_tools.resolve())
    assert service.offline_path == str(new_tools.resolve())
    assert values_changed.count() == 1
    assert command_changed.count() == 1


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
    model.reload()

    assert model.rulesDir == "second"
    assert model.dirty is False


def test_config_save_rejects_external_changes(qapp, tmp_path) -> None:
    model, api = config_model("rules_dir: original\nretries: 5\n")

    model.setValue("rules_dir", "draft")
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

    model.setValue("rules_dir", "original")
    model.save()

    assert changed.count() == 0
    assert model.dirty is False
    assert api.source == original
    assert api.replace_count == 0


def test_non_finite_rule_number_is_rejected(qapp, tmp_path) -> None:
    catalog = RuleCatalogService(list_runner=lambda _request: RuleCatalogResult())
    model = RuleViewModel(rule_catalog=catalog)
    model.setSource("version: '1.0'\nregex: '(.*)'\ncolumns: [value]\nretries: 5\n")

    for value in (math.nan, math.inf, -math.inf):
        model.setVisualNumber("/retries", value)
        model.selectNode("/retries")
        assert model.selectedNode["rawValue"] == 5


def test_catalog_refresh_and_scalar_edit_do_not_reset_rule_tree(qapp) -> None:
    catalog = RuleCatalogService(list_runner=lambda _request: RuleCatalogResult())
    model = RuleViewModel(rule_catalog=catalog)
    resets = QSignalSpy(model.documentReset)
    catalog_changes = QSignalSpy(model.catalogChanged)
    node_changes = QSignalSpy(model.nodeDataChanged)

    model.setNodeExpanded("/columns", True)
    catalog.refresh()
    model.setVisualValue("/version", "2.0")

    assert resets.count() == 0
    assert catalog_changes.count() == 1
    assert node_changes.count() == 1
    assert model.expandedPointers == ["/columns"]


def test_list_mutations_remap_selection_to_original_item(qapp) -> None:
    catalog = RuleCatalogService(list_runner=lambda _request: RuleCatalogResult())
    model = RuleViewModel(rule_catalog=catalog)
    model.setSource("version: '1.0'\nregex: '(.*),(.*)'\ncolumns: [first, second]\n")
    model.selectNode("/columns/0")

    model.moveEntry("/columns/0", 1)

    assert model.selectedPointer == "/columns/1"
    assert model.selectedNode["rawValue"] == "first"

    model.selectNode("/columns")
    model.addListItem()
    assert model.selectedPointer == "/columns/2"

    model.removeEntry("/columns/2")
    assert model.selectedPointer == "/columns"


def test_command_fields_hide_internal_offline_action_and_filter_plot_options(
    qapp, tmp_path
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    model = AppViewModel(settings)
    model.selectCommand("offline")
    assert "do_list" not in {field["name"] for field in model.currentFields}

    model.selectCommand("plot")
    model.setValue("plot_type", "psd")
    psd_fields = {field["name"] for field in model.currentFields}
    assert "psd_acc" in psd_fields
    assert "freq_range" not in psd_fields

    model.setValue("plot_type", "fft")
    fft_fields = {field["name"] for field in model.currentFields}
    assert "freq_range" in fft_fields
    assert "psd_acc" not in fft_fields
