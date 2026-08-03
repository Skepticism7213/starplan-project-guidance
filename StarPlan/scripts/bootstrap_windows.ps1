[CmdletBinding()]
param(
    [switch]$ForceInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirements = Join-Path $projectRoot "requirements.txt"
$marker = Join-Path $venvRoot ".starplan-requirements.sha256"

if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw "requirements.txt was not found under $projectRoot"
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $basePython = $env:STARPLAN_PYTHON
    if ([string]::IsNullOrWhiteSpace($basePython)) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python was not found. Install Python 3.10+ or set STARPLAN_PYTHON to python.exe."
        }
        $basePython = $pythonCommand.Source
    }

    Write-Host "[ENV] Creating project virtual environment: $venvRoot"
    & $basePython -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Python virtual environment creation failed with exit code $LASTEXITCODE"
    }
}

$requiredHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash.ToLowerInvariant()
$installedHash = ""
if (Test-Path -LiteralPath $marker -PathType Leaf) {
    $installedHash = (Get-Content -LiteralPath $marker -Raw -Encoding ASCII).Trim().ToLowerInvariant()
}

$needsInstall = $ForceInstall -or $requiredHash -ne $installedHash
if ($needsInstall) {
    Write-Host "[ENV] Installing requirements (one time for this requirements hash)"
    & $venvPython -X utf8 -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host "[ENV] Reusing existing dependencies for requirements hash $requiredHash"
}

& $venvPython -X utf8 -c "import astropy, astroplan, dashscope, matplotlib, numpy, pydantic, pytest, yaml, dotenv, sys; print('[ENV] Python ' + sys.version.split()[0]); print('[ENV] Executable ' + sys.executable)"
if ($LASTEXITCODE -ne 0) {
    throw "The project Python environment is missing a required dependency"
}

if ($needsInstall) {
    Set-Content -LiteralPath $marker -Value $requiredHash -Encoding ASCII -NoNewline
}

Write-Host "[ENV] Ready. Use scripts\run_utf8.ps1 for script entry points."
