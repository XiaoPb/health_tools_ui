from __future__ import annotations

import math

from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy

from health_tools_ui.config_service import HealthConfigService
from health_tools_ui.viewmodels import AppViewModel, RuleViewModel


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
    user_config = tmp_path / "user" / "config.yaml"
    user_config.parent.mkdir()
    user_config.write_text("rules_dir: first\n", encoding="utf-8")
    model = RuleViewModel(config_service=HealthConfigService(user_config=user_config))

    user_config.write_text("rules_dir: second\n", encoding="utf-8")
    model.requestOpenConfig()

    assert model.kind == "config"
    assert model.selectedNode["kind"] == "mapping"
    model.selectNode("/rules_dir")
    assert model.selectedNode["rawValue"] == "second"
    assert model.dirty is False


def test_config_save_rejects_external_changes(qapp, tmp_path) -> None:
    user_config = tmp_path / "user" / "config.yaml"
    user_config.parent.mkdir()
    user_config.write_text("rules_dir: original\nretries: 5\n", encoding="utf-8")
    model = RuleViewModel(config_service=HealthConfigService(user_config=user_config))

    model.setVisualValue("/rules_dir", "draft")
    user_config.write_text("rules_dir: external\nretries: 5\n", encoding="utf-8")
    model.save()

    assert user_config.read_text(encoding="utf-8").startswith("rules_dir: external")
    assert model.dirty is True
    assert "extern" in model.status.lower() or "外部" in model.status


def test_equal_config_edit_and_clean_save_do_not_write(qapp, tmp_path) -> None:
    user_config = tmp_path / "user" / "config.yaml"
    user_config.parent.mkdir()
    original = "rules_dir: original\n"
    user_config.write_text(original, encoding="utf-8")
    model = RuleViewModel(config_service=HealthConfigService(user_config=user_config))
    changed = QSignalSpy(model.documentChanged)
    modified_at = user_config.stat().st_mtime_ns

    model.setVisualValue("/rules_dir", "original")
    model.save()

    assert changed.count() == 0
    assert model.dirty is False
    assert user_config.read_text(encoding="utf-8") == original
    assert user_config.stat().st_mtime_ns == modified_at


def test_non_finite_rule_number_is_rejected(qapp, tmp_path) -> None:
    user_config = tmp_path / "user" / "config.yaml"
    user_config.parent.mkdir()
    user_config.write_text("rules_dir: original\nretries: 5\n", encoding="utf-8")
    model = RuleViewModel(config_service=HealthConfigService(user_config=user_config))

    for value in (math.nan, math.inf, -math.inf):
        model.setVisualNumber("/retries", value)
        model.selectNode("/retries")
        assert model.selectedNode["rawValue"] == 5
        assert model.dirty is False
