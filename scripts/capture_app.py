from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyhuskarui.husapp import HusApp
from PySide6.QtCore import QObject, QSettings, QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from health_tools_ui.config_service import HealthConfigService
from health_tools_ui.resources import RuleCatalogService
from health_tools_ui.rule_generation.viewmodel import RuleGeneratorViewModel
from health_tools_ui.viewmodels import AppViewModel, ConfigViewModel, RuleViewModel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--page", choices=("command", "rules", "config", "settings"), default="command"
    )
    parser.add_argument("--command", default="parse")
    parser.add_argument("--rule-kind", default="parse")
    parser.add_argument(
        "--rule-mode", choices=("library", "generator", "editor"), default="library"
    )
    parser.add_argument("--sample", default="")
    parser.add_argument("--target-chip", default="")
    parser.add_argument("--locale", choices=("zh_CN", "en"), default="zh_CN")
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda warnings: [print(warning.toString(), file=sys.stderr) for warning in warnings]
    )
    HusApp.initialize(engine)
    config_service = HealthConfigService()
    rule_catalog = RuleCatalogService(engine)
    app_model = AppViewModel(QSettings(), engine, rule_catalog, config_service)
    rule_model = RuleViewModel(engine, rule_catalog, config_service)
    config_model = ConfigViewModel(engine, config_service)
    generator_model = RuleGeneratorViewModel(engine, rule_catalog)
    app_model.setLocale(args.locale)
    app_model.setDarkMode(args.dark)
    engine.rootContext().setContextProperty("appModel", app_model)
    engine.rootContext().setContextProperty("ruleModel", rule_model)
    engine.rootContext().setContextProperty("configModel", config_model)
    engine.rootContext().setContextProperty("generatorModel", generator_model)
    qml = Path(__file__).parents[1] / "src" / "health_tools_ui" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    app_model.selectCommand(args.command)
    if args.rule_mode == "editor":
        rule_model.newDocument(args.rule_kind)
    generator_model.setKind(args.rule_kind)
    if args.sample:
        generator_model.loadSample(args.sample)
    window.setWidth(args.width)
    window.setHeight(args.height)
    window.setProperty("currentPage", args.page)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def prepare() -> None:
        if args.page == "rules":
            rule_center = window.findChild(QObject, "ruleCenter")
            if rule_center is not None:
                rule_center.setProperty("workspaceMode", args.rule_mode)
        if args.target_chip:
            generator_model.setTargetChip(args.target_chip)
        QTimer.singleShot(900, capture)

    def capture() -> None:
        image = window.grabWindow()
        if image.isNull() or not image.save(str(args.output)):
            app.exit(2)
            return
        app.exit(0)

    QTimer.singleShot(600, prepare)
    result = app.exec()
    generator_model.cleanup()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
