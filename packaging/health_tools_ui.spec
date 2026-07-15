# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

root = Path(SPECPATH).parent
pyhuskarui_data, pyhuskarui_binaries, pyhuskarui_hidden = collect_all("pyhuskarui")
health_data = collect_data_files("health_tools")
health_hidden = collect_submodules(
    "health_tools",
    filter=lambda name: not name.startswith("health_tools.ui")
    and name != "health_tools.commands.ui",
)

a = Analysis(
    [str(root / "packaging" / "entrypoint.py")],
    pathex=[str(root / "src")],
    binaries=pyhuskarui_binaries,
    datas=pyhuskarui_data + health_data + [
        (str(root / "src" / "health_tools_ui" / "qml"), "health_tools_ui/qml"),
        (str(root / "src" / "health_tools_ui" / "i18n"), "health_tools_ui/i18n"),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=pyhuskarui_hidden + health_hidden,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HealthToolsUI",
    console=False,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="HealthToolsUI")
