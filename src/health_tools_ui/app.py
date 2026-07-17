from __future__ import annotations

import sys
from pathlib import Path

from pyhuskarui.husapp import HusApp
from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from . import __version__
from .config_service import HealthConfigService
from .resources import RuleCatalogService
from .viewmodels import AppViewModel, RuleViewModel


def run_app(argv: list[str] | None = None) -> int:
    QApplication.setOrganizationName("XiaoPb")
    QApplication.setOrganizationDomain("github.com/XiaoPb")
    QApplication.setApplicationName("HealthToolsUI")
    QApplication.setApplicationDisplayName("Health Tools UI")
    QApplication.setApplicationVersion(__version__)

    app = QApplication(argv or sys.argv)
    icon_path = Path(__file__).parent / "assets" / "app-icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    engine = QQmlApplicationEngine()
    engine.warnings.connect(
        lambda warnings: [print(warning.toString(), file=sys.stderr) for warning in warnings]
    )
    HusApp.initialize(engine)

    settings = QSettings()
    config_service = HealthConfigService()
    config_service.initialize_and_sync()
    rule_catalog = RuleCatalogService(engine)
    app_model = AppViewModel(settings, engine, rule_catalog, config_service)
    rule_model = RuleViewModel(engine, rule_catalog, config_service)
    engine.rootContext().setContextProperty("appModel", app_model)
    engine.rootContext().setContextProperty("ruleModel", rule_model)

    qml_path = Path(__file__).parent / "qml" / "Main.qml"
    url = QUrl.fromLocalFile(str(qml_path))
    engine.objectCreated.connect(
        lambda obj, obj_url: sys.exit(1) if obj is None and obj_url == url else None,
        Qt.ConnectionType.QueuedConnection,
    )
    engine.load(url)
    if not engine.rootObjects():
        return 1
    result = app.exec()
    del engine
    return result
