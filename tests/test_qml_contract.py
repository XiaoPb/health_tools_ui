from __future__ import annotations

from pathlib import Path


def test_analysis_menus_are_before_parse_and_use_presets() -> None:
    source = (Path(__file__).parents[1] / "src" / "health_tools_ui" / "qml" / "Main.qml").read_text(
        encoding="utf-8"
    )

    assert source.index('key: "analyze:hr"') < source.index('key: "cmd:parse"')
    assert source.index('key: "analyze:spo2"') < source.index('key: "cmd:parse"')
    assert 'appModel.selectAnalysis("hr")' in source
    assert 'appModel.selectAnalysis("spo2")' in source


def test_rule_and_config_tables_define_text_cell_delegates() -> None:
    qml_dir = Path(__file__).parents[1] / "src" / "health_tools_ui" / "qml"
    rule_source = (qml_dir / "RuleCenter.qml").read_text(encoding="utf-8")
    config_source = (qml_dir / "ConfigPage.qml").read_text(encoding="utf-8")

    assert rule_source.count("delegate: tableTextCell") == 6
    assert config_source.count("delegate: tableTextCell") == 4
    assert "contentWidth: availableWidth" in config_source
    assert "width: pathsScroll.availableWidth" in config_source
