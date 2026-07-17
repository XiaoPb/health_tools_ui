from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyhuskarui.husapp import HusApp
from PySide6.QtCore import QSettings, QUrl, qInstallMessageHandler
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from health_tools_ui.config_service import HealthConfigService
from health_tools_ui.resources import RuleCatalogService
from health_tools_ui.rule_generation.viewmodel import RuleGeneratorViewModel
from health_tools_ui.viewmodels import AppViewModel, ConfigViewModel, RuleViewModel

app = QApplication.instance() or QApplication(sys.argv)
qt_messages: list[str] = []
qInstallMessageHandler(lambda _mode, _context, message: qt_messages.append(message))
engine = QQmlApplicationEngine()
HusApp.initialize(engine)
config_service = HealthConfigService()
rule_catalog = RuleCatalogService(engine)
app_model = AppViewModel(QSettings(), engine, rule_catalog, config_service)
rule_model = RuleViewModel(engine, rule_catalog, config_service)
config_model = ConfigViewModel(engine, config_service)
generator_model = RuleGeneratorViewModel(engine, rule_catalog)
engine.rootContext().setContextProperty("appModel", app_model)
engine.rootContext().setContextProperty("ruleModel", rule_model)
engine.rootContext().setContextProperty("configModel", config_model)
engine.rootContext().setContextProperty("generatorModel", generator_model)
path = Path(__file__).parents[1] / "src" / "health_tools_ui" / "qml" / "Main.qml"
engine.load(QUrl.fromLocalFile(str(path)))
if not engine.rootObjects():
    print("\n".join(qt_messages), file=sys.stderr)
    raise SystemExit("QML root object failed to load")
app.processEvents()
root = engine.rootObjects()[0]
for page in ("rules", "config", "settings", "command"):
    root.setProperty("currentPage", page)
    app.processEvents()
runtime_errors = [
    message
    for message in qt_messages
    if any(
        marker in message
        for marker in (
            "TypeError",
            "Binding loop",
            "recursive rearrange",
            "is not defined",
            "Unable to assign",
        )
    )
]
if runtime_errors:
    print("\n".join(runtime_errors), file=sys.stderr)
    raise SystemExit("QML runtime errors detected")
print("QML smoke test passed")
generator_model.cleanup()
