$ErrorActionPreference = "Stop"
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run python scripts/qml_smoke.py
uv run pyinstaller packaging/health_tools_ui.spec --noconfirm
New-Item -ItemType Directory -Force dist/HealthToolsUI/offline | Out-Null
$version = (uv run python -c "import importlib.metadata as m; print(m.version('health-tools-ui'))").Trim()
$portable = "dist/health-tools-ui-$version-windows-x64.zip"
Compress-Archive -Force -Path dist/HealthToolsUI/* -DestinationPath $portable
Write-Host "Portable build: $portable"
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if ($iscc) {
    & $iscc.Source "/DMyAppVersion=$version" "/DMyOutputBaseFilename=health-tools-ui-setup-$version" packaging/installer.iss
    Write-Host "Installer: dist/health-tools-ui-setup-$version.exe"
} else {
    Write-Host "Inno Setup not found; skipped installer build."
}
