[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ScriptPath,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgument
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & (Join-Path $PSScriptRoot "bootstrap_windows.ps1")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw "The project environment could not be prepared"
    }
}

if ([IO.Path]::IsPathRooted($ScriptPath)) {
    $resolvedScript = $ScriptPath
} else {
    $resolvedScript = Join-Path $projectRoot $ScriptPath
}
if (-not (Test-Path -LiteralPath $resolvedScript -PathType Leaf)) {
    throw "Python script was not found: $resolvedScript"
}

& $venvPython -X utf8 $resolvedScript @ScriptArgument
exit $LASTEXITCODE
