from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pyhuskarui.husapp import HusApp
from PySide6.QtCore import QSettings, QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from health_tools_ui.viewmodels import AppViewModel, RuleViewModel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--page", choices=("command", "rules", "settings"), default="command")
    parser.add_argument("--command", default="parse")
    parser.add_argument("--rule-kind", default="config")
    parser.add_argument("--locale", choices=("zh_CN", "en"), default="zh_CN")
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()

    app = QApplication(sys.argv[:1])
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda warnings: [print(warning.toString(), file=sys.stderr) for warning in warnings]
    )
    HusApp.initialize(engine)
    app_model = AppViewModel(QSettings(), engine)
    rule_model = RuleViewModel(engine)
    app_model.setLocale(args.locale)
    app_model.setDarkMode(args.dark)
    engine.rootContext().setContextProperty("appModel", app_model)
    engine.rootContext().setContextProperty("ruleModel", rule_model)
    qml = Path(__file__).parents[1] / "src" / "health_tools_ui" / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    app_model.selectCommand(args.command)
    if args.rule_kind == "config":
        rule_model.openConfig()
    else:
        rule_model.newDocument(args.rule_kind)
    window.setWidth(args.width)
    window.setHeight(args.height)
    window.setProperty("currentPage", args.page)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def capture() -> None:
        image = window.grabWindow()
        if image.isNull() or not image.save(str(args.output)):
            app.exit(2)
            return
        app.exit(0)

    QTimer.singleShot(1500, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
