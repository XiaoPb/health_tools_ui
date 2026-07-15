$ErrorActionPreference = "Stop"
uv sync --locked --group dev
uv run pytest
uv run ruff check .
uv run python scripts/qml_smoke.py
uv run pyinstaller packaging/health_tools_ui.spec --noconfirm
New-Item -ItemType Directory -Force dist/HealthToolsUI/offline | Out-Null
Compress-Archive -Force -Path dist/HealthToolsUI/* -DestinationPath dist/HealthToolsUI-portable.zip
Write-Host "Portable build: dist/HealthToolsUI-portable.zip"
