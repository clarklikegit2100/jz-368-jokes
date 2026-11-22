<#
.SYNOPSIS
  Build the daily project report and send it to Telegram. Called by Windows Task Scheduler.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File project_agent\windows\run_report.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File project_agent\windows\run_report.ps1 -DryRun
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoLlm
)

$ErrorActionPreference = "Stop"
$AgentDir = Split-Path -Parent $PSScriptRoot          # ...\project_agent
$RepoRoot = Split-Path -Parent $AgentDir              # ...\jz-368-jokes
Set-Location $RepoRoot

$LogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir ("project-report-{0}.log" -f (Get-Date -Format "yyyy-MM"))

function Write-Log([string]$Text) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Text
    Write-Output $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# Load secrets from .env in the repo root (same file as the joke bot), then project_agent\.env if present.
foreach ($EnvFile in (Join-Path $RepoRoot ".env"), (Join-Path $AgentDir ".env")) {
    if (-not (Test-Path $EnvFile)) { continue }
    foreach ($raw in Get-Content -Path $EnvFile -Encoding UTF8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { continue }
        $name, $value = $line.Split("=", 2)
        $name = $name.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path ("Env:" + $name) -Value $value }
    }
}

# Pick a Python: REPORT_PYTHON, then JOKE_PYTHON, then the py launcher, then python on PATH.
$PythonCmd = @()
if ($env:REPORT_PYTHON) {
    $PythonCmd = @($env:REPORT_PYTHON)
} elseif ($env:JOKE_PYTHON) {
    $PythonCmd = @($env:JOKE_PYTHON)
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = @("py", "-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = @("python")
} else {
    Write-Log "ERROR: Python not found. Install Python 3 or set REPORT_PYTHON in .env to the full path of python.exe."
    exit 3
}

$env:PYTHONIOENCODING = "utf-8"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$PyArgs = @("project_agent\project_report.py")
if ($DryRun) { $PyArgs += "--dry-run" }
if ($NoLlm) { $PyArgs += "--no-llm" }

$Exe = $PythonCmd[0]
$ExeArgs = @()
if ($PythonCmd.Count -gt 1) { $ExeArgs = $PythonCmd[1..($PythonCmd.Count - 1)] }
$ExeArgs += $PyArgs

Write-Log ("Running: {0} {1}" -f $Exe, ($ExeArgs -join " "))
$ErrorActionPreference = "Continue"
$output = & $Exe @ExeArgs 2>&1
$code = $LASTEXITCODE
foreach ($o in $output) { Write-Log ([string]$o) }
if ($code -ne 0) {
    Write-Log "FAILED with exit code $code"
    exit $code
}
Write-Log "OK"
exit 0
