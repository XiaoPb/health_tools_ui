[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $UvArguments = @("run", "health-tools-ui")
)

$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$venvPath = [IO.Path]::GetFullPath((Join-Path $projectRoot ".venv"))
$uv = (Get-Command uv.exe -ErrorAction Stop).Source
$environmentNames = @(
    "PATH",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "CONDA_PROMPT_MODIFIER",
    "VIRTUAL_ENV",
    "PYTHONHOME",
    "PYTHONPATH",
    "QT_PLUGIN_PATH",
    "QML2_IMPORT_PATH",
    "UV_PYTHON",
    "UV_PYTHON_PREFERENCE",
    "UV_PROJECT_ENVIRONMENT"
)
$savedEnvironment = @{}
foreach ($name in $environmentNames) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

try {
    $blockedPath = "\\(?:anaconda3|miniconda3|miniforge3|mambaforge)(?:\\|$)|\\Qt\\"
    $cleanPath = $env:PATH -split ";" | Where-Object {
        $_ -and $_ -notmatch $blockedPath
    }
    foreach ($name in $environmentNames | Where-Object { $_ -ne "PATH" }) {
        Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    }

    $managedPythonDirOutput = & $uv python dir
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to locate the uv managed Python directory."
    }
    $managedPythonDir = ([string]$managedPythonDirOutput).Trim()
    $pythonOutput = & $uv python find --managed-python 3.12.12 --directory $managedPythonDir
    if ($LASTEXITCODE -ne 0) {
        throw "uv-managed CPython 3.12.12 is unavailable. Run: uv python install 3.12.12"
    }
    $python = ([string]$pythonOutput).Trim()
    if (-not (Test-Path -LiteralPath $python)) {
        throw "uv returned an invalid CPython path: $python"
    }

    $env:PATH = (@((Split-Path -Parent $python)) + $cleanPath) -join ";"
    $env:UV_PYTHON = $python
    $env:UV_PROJECT_ENVIRONMENT = $venvPath

    $configuration = Join-Path $venvPath "pyvenv.cfg"
    $expectedHome = [Regex]::Escape((Split-Path -Parent $python))
    $needsRebuild = -not (Test-Path -LiteralPath $configuration)
    if (-not $needsRebuild) {
        $needsRebuild = (Get-Content -Raw -LiteralPath $configuration) -notmatch $expectedHome
    }
    if ($needsRebuild) {
        if (-not $venvPath.StartsWith($projectRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to rebuild a virtual environment outside the project: $venvPath"
        }
        Write-Host "Rebuilding .venv with uv-managed CPython 3.12.12..."
        & $uv venv --clear --python $python $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "uv failed to rebuild the project environment (exit code $LASTEXITCODE)."
        }
    }

    Push-Location $projectRoot
    if ($UvArguments.Count -gt 0 -and $UvArguments[0] -eq "sync-local") {
        $extraSyncArguments = @($UvArguments | Select-Object -Skip 1)
        & $uv sync --group dev --default-index https://pypi.tuna.tsinghua.edu.cn/simple @extraSyncArguments
        $uvExitCode = $LASTEXITCODE
        if ($uvExitCode -eq 0) {
            & $uv lock --default-index https://pypi.org/simple --quiet
            $uvExitCode = $LASTEXITCODE
        }
    }
    elseif ($UvArguments.Count -gt 0 -and $UvArguments[0] -eq "run") {
        $runArguments = @("run", "--no-sync") + @($UvArguments | Select-Object -Skip 1)
        & $uv @runArguments
        $uvExitCode = $LASTEXITCODE
    }
    else {
        & $uv @UvArguments
        $uvExitCode = $LASTEXITCODE
    }
    Pop-Location
    if ($uvExitCode -ne 0) {
        throw "uv command failed with exit code $uvExitCode."
    }
}
finally {
    foreach ($name in $environmentNames) {
        if ($null -eq $savedEnvironment[$name]) {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], "Process")
        }
    }
}
